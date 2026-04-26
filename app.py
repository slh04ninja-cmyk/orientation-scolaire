import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

from utils import (
    TRACK_ORDER,
    TRACK_NAMES,
    TRACK_COLORS,
    DEFAULT_WEIGHTS,
    DEFAULT_THRESHOLDS,
    SUBJECT_ABBREV,
    read_excel_safe,
    clean_dataframe,
    detect_subject_columns,
    build_student_name,
    compute_averages,
    compute_student_score,
    classify_all,
    extract_massar_metadata,
    process_multiple_files,        # nouvelle fonction
    get_css,
    html_header,
    html_welcome,
    html_seuil_scale,
    html_stat_card,
    help_text,
)

# ── Support arabe pour PDF ──
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Enregistrer DejaVu Sans (supporte l'arabe) — chemin relatif au dossier du script
import os
_FONT_DIR = os.path.dirname(os.path.abspath(__file__))
pdfmetrics.registerFont(TTFont('DejaVu', os.path.join(_FONT_DIR, 'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DejaVu-Bold', os.path.join(_FONT_DIR, 'DejaVuSans-Bold.ttf')))


def reshape_arabic(text):
    """Reshape et reorder le texte arabe pour affichage correct dans PDF"""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)

st.set_page_config(
    page_title="Orientation Scolaire",
    page_icon="\U0001F393",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown("<style>" + get_css() + "</style>", unsafe_allow_html=True)
st.markdown(html_header(), unsafe_allow_html=True)


def generate_pdf_report(results_df, matieres_list, classe):
    """Génère un rapport PDF avec pagination, numéro d'élève, noms en arabe"""
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=15*mm, bottomMargin=15*mm,
        leftMargin=12*mm, rightMargin=12*mm,
    )
    story = []

    # ── Styles ──
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=16, textColor=colors.HexColor("#7c6cf0"),
        spaceAfter=10, alignment=1, fontName='DejaVu-Bold',
    )
    heading_style = ParagraphStyle(
        'CustomHeading', parent=styles['Heading2'],
        fontSize=11, textColor=colors.HexColor("#333333"),
        spaceAfter=8, fontName='DejaVu-Bold',
    )
    normal_style = ParagraphStyle(
        'CustomNormal', parent=styles['Normal'],
        fontSize=9, fontName='DejaVu',
    )
    cell_style = ParagraphStyle(
        'CellStyle', parent=styles['Normal'],
        fontSize=8, fontName='DejaVu', leading=10,
    )
    cell_center = ParagraphStyle(
        'CellCenter', parent=cell_style, alignment=1,
    )
    cell_arabic = ParagraphStyle(
        'CellArabic', parent=cell_style, alignment=2,  # droite pour arabe
    )

    # ── Titre ──
    story.append(Paragraph("Rapport d'Orientation Scolaire", title_style))
    story.append(Spacer(1, 4*mm))

    # ── Infos classe ──
    matieres_text = ", ".join(matieres_list) if isinstance(matieres_list, list) else str(matieres_list)
    story.append(Paragraph(f"Classe : {classe} | Matieres : {matieres_text}", heading_style))
    story.append(Spacer(1, 4*mm))

    # ── Colonnes : N° | N° Massar | Élève (arabe) | Score | Éligibilité ──
    col_widths = [10*mm, 28*mm, 55*mm, 18*mm, 55*mm]
    header_row = [
        Paragraph("<b>N°</b>", cell_center),
        Paragraph("<b>N° Massar</b>", cell_center),
        Paragraph("<b>Eleve</b>", cell_center),
        Paragraph("<b>Score</b>", cell_center),
        Paragraph("<b>Eligibilite</b>", cell_center),
    ]

    ROWS_PER_PAGE = 35
    total_students = len(results_df)
    all_rows = []

    for i, (_, row) in enumerate(results_df.iterrows()):
        nom_arabe = str(row.get("Eleve", ""))
        nom_display = reshape_arabic(nom_arabe)
        num_massar = str(row.get("Num_Massar", ""))
        score_val = f"{row.get('Score', 0):.1f}"
        elig_val = str(row.get("Eligibilite", ""))

        data_row = [
            Paragraph(str(i + 1), cell_center),
            Paragraph(num_massar, cell_center),
            Paragraph(nom_display, cell_arabic),
            Paragraph(score_val, cell_center),
            Paragraph(elig_val, cell_center),
        ]
        all_rows.append(data_row)

    # ── Paginer et construire les tables ──
    for page_start in range(0, total_students, ROWS_PER_PAGE):
        page_end = min(page_start + ROWS_PER_PAGE, total_students)
        page_rows = all_rows[page_start:page_end]

        table_data = [header_row] + page_rows
        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#7c6cf0")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            # Corps
            ('FONTNAME', (0, 1), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),   # N°
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),    # N° Massar
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),    # Score
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),    # Eligibilité
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),     # Nom arabe (RTL)
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # Grille
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8fc")]),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ]))

        story.append(table)

        # Info pagination
        page_num = page_start // ROWS_PER_PAGE + 1
        total_pages = (total_students + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f"Page {page_num}/{total_pages} — Eleves {page_start+1}-{page_end} sur {total_pages} pages",
            ParagraphStyle('PageInfo', parent=normal_style, alignment=1, textColor=colors.grey, fontSize=7),
        ))

        if page_end < total_students:
            story.append(PageBreak())

    # ── Stats finales ──
    story.append(Spacer(1, 6*mm))
    stats = f"Total : {total_students} eleves"
    story.append(Paragraph(stats, heading_style))

    # Seuils
    seuils_info = "Seuils : SM ≥ 70 | SE ≥ 50 | LT ≥ 30"
    story.append(Paragraph(seuils_info, normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ─────────────────────────────────────────────
# SIDEBAR – UPLOAD
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")
    st.divider()

    uploaded_files = st.file_uploader(
        "Importer les fichiers Excel (un par matière)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
    )
    st.divider()

# ─────────────────────────────────────────────
# PAGE D'ACCUEIL — aucun fichier
# ─────────────────────────────────────────────
if not uploaded_files:
    st.markdown(html_welcome(), unsafe_allow_html=True)
    st.markdown("### Exemple de format attendu")
    sample = pd.DataFrame({
        "Nom": ["Dupont", "Martin", "Bernard"],
        "Prenom": ["Marie", "Ahmed", "Sophie"],
        "Physique_DS1": [14, 12, 8],
        "Physique_DS2": [15, 11, 9],
        "Physique_DS3": [13, 13, 7],
        "Math_DS1": [16, 10, 12],
        "Math_DS2": [17, 11, 11],
        "Math_DS3": [15, 9, 10],
        "SVT_DS1": [10, 15, 13],
        "SVT_DS2": [11, 16, 14],
        "SVT_DS3": [9, 14, 12],
        "Francais_DS1": [12, 11, 16],
        "Francais_DS2": [11, 10, 17],
        "Francais_DS3": [13, 12, 18],
    })
    st.dataframe(sample, use_container_width=True)
    st.stop()

# ─────────────────────────────────────────────
# TRAITEMENT DES FICHIERS
# ─────────────────────────────────────────────
try:
    df_merged, matieres_detectees, classe, devoirs_par_matiere, massar_ids = process_multiple_files(uploaded_files)
    st.success(f"✅ {len(df_merged)} élèves chargés | Matières : {', '.join(matieres_detectees)} | Classe : {classe}")

    # Debug: afficher les premières lignes
    with st.expander("🔍 Données extraites (debug)"):
        st.dataframe(df_merged.head(10))
        st.write(f"Colonnes : {list(df_merged.columns)}")
        st.write(f"massar_ids : {len(massar_ids)} entrées")
        st.write(f"devoirs_par_matiere : {devoirs_par_matiere}")
except Exception as exc:
    st.error("Impossible de lire/combiner les fichiers : " + str(exc))
    st.stop()

# ─────────────────────────────────────────────
# SIDEBAR – POIDS & SEUILS (après détection)
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("#### Poids des matières")
    st.caption("Ces poids s'appliquent à toutes les filières pour calculer le score unique.")

    WEIGHTS = {}
    for matiere in matieres_detectees:
        default_val = DEFAULT_WEIGHTS.get(matiere, 1.0)
        key = f"w_{matiere.replace(' ', '_')}"
        WEIGHTS[matiere] = st.slider(
            matiere, 0.0, 5.0, default_val, 0.5, key=key
        )
    total_w = sum(WEIGHTS.values())
    if total_w == 0:
        st.error("Les poids ne peuvent pas être tous à zéro.")

    with st.expander("Résumé des poids"):
        wdf = pd.DataFrame(
            {"Matière": list(WEIGHTS.keys()), "Poids": list(WEIGHTS.values())}
        )
        wdf["Part (%)"] = (wdf["Poids"] / total_w * 100).round(1) if total_w > 0 else 0
        st.dataframe(wdf, use_container_width=True, hide_index=True)

    st.divider()

    st.markdown("#### Seuils d'éligibilité")
    st.caption("Entrez le score minimum /100 requis pour chaque filière.")

    col_sm, col_se, col_lt = st.columns(3)
    with col_sm:
        seuil_sm = st.number_input(
            "SM", min_value=0, max_value=100,
            value=DEFAULT_THRESHOLDS["SM"], step=1, key="s_sm",
            help="Score minimum pour Sciences Mathématiques"
        )
    with col_se:
        seuil_se = st.number_input(
            "SE", min_value=0, max_value=100,
            value=DEFAULT_THRESHOLDS["SE"], step=1, key="s_se",
            help="Score minimum pour Sciences Expérimentales"
        )
    with col_lt:
        seuil_lt = st.number_input(
            "LT", min_value=0, max_value=100,
            value=DEFAULT_THRESHOLDS["LT"], step=1, key="s_lt",
            help="Score minimum pour Lettres et Traduction"
        )

    THRESHOLDS = {"SM": seuil_sm, "SE": seuil_se, "LT": seuil_lt}

    if not (seuil_sm > seuil_se > seuil_lt):
        st.warning("Recommandé : SM > SE > LT pour une orientation discriminante.")

    st.markdown(html_seuil_scale(seuil_sm, seuil_se, seuil_lt), unsafe_allow_html=True)

    st.divider()
    with st.expander("Comment ça marche"):
        st.markdown(help_text())

# ─────────────────────────────────────────────
#  DÉTECTION AUTOMATIQUE
# ─────────────────────────────────────────────
st.markdown("### Détection automatique")

info_col1, info_col2, info_col3 = st.columns(3)
with info_col1:
    st.markdown(f"### 📚 {', '.join(matieres_detectees)}")
    st.caption(f"Classe : {classe}")
with info_col2:
    st.markdown("**Devoirs détectés :**")
    for matiere, nb in devoirs_par_matiere.items():
        st.markdown(f"- **{matiere}** — {nb} devoir(s)")
with info_col3:
    nb_eleves = len(df_merged)
    st.markdown(f"- **Élèves :** {nb_eleves}")

st.divider()

# ─────────────────────────────────────────────
#  CALCUL DES SCORES
# ─────────────────────────────────────────────
# Séparer les noms et les moyennes
student_names = df_merged["Eleve"]
averages = df_merged.drop(columns=["Eleve"]).set_index(df_merged["Eleve"])

scores = compute_student_score(averages, WEIGHTS)

if scores.empty or len(averages) == 0:
    st.error("Aucune donnée élève trouvée. Vérifiez le format de vos fichiers.")
    st.stop()

results = classify_all(student_names, averages, scores, THRESHOLDS)

# Ajouter le numéro MASSAR aux résultats
results["Num_Massar"] = results["Eleve"].map(massar_ids).fillna("")

# ─────────────────────────────────────────────
#  STATISTIQUES
# ─────────────────────────────────────────────
st.markdown("### Statistiques")

total = len(results)
count_sm = int(results["Eligibilite"].str.contains("SM", na=False).sum())
count_se = int(results["Eligibilite"].str.contains("SE", na=False).sum())
count_lt = int(results["Eligibilite"].str.contains("LT", na=False).sum())

stat_items = [
    (count_sm, "#7c6cf0", f"Eligibles SM (≥ {seuil_sm})"),
    (count_se, "#22c997", f"Eligibles SE (≥ {seuil_se})"),
    (count_lt, "#f06292", f"Eligibles LT (≥ {seuil_lt})"),
]

cols_cards = st.columns(3)
for col, (count, color, subtitle) in zip(cols_cards, stat_items):
    pct = f"{round(count / total * 100, 1)} %" if total else "---"
    with col:
        st.markdown(html_stat_card(count, color, subtitle, pct), unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────
#  TABLEAU DES RÉSULTATS
# ─────────────────────────────────────────────
st.markdown("### Résultats détaillés (triés par score)")

filtre = st.multiselect(
    "Filtrer par éligibilité",
    ["SM", "SE", "LT", "Aucune"],
    default=["SM", "SE", "LT", "Aucune"],
)

def _match_filtre(row):
    if row["Eligibilite"] == "Aucune":
        return "Aucune" in filtre
    return any(f in row["Eligibilite"] for f in filtre)

filtered = results[results.apply(_match_filtre, axis=1)].copy()

# Suppression colonnes non souhaitées
cols_to_drop = [c for c in ["Filiere principale", "Nb filieres"] if c in filtered.columns]
filtered = filtered.drop(columns=cols_to_drop)

# ✅ RENOMMER les colonnes "Moy. ..." avec abréviations français
rename_mapping = {}
for col in filtered.columns:
    if col.startswith("Moy. "):
        matiere = col.replace("Moy. ", "")
        abbrev = SUBJECT_ABBREV.get(matiere, col)
        rename_mapping[col] = abbrev

filtered = filtered.rename(columns=rename_mapping)

# Formatage
fmt = {"Score": "{:.2f}"}
for c in filtered.columns:
    if c.startswith("moy."):
        fmt[c] = "{:.2f}"

def _style_eligibilite(val):
    if "SM" in str(val):
        return "color:#b8b0ff;font-weight:600"
    if "SE" in str(val):
        return "color:#7aebc8;font-weight:600"
    if "LT" in str(val):
        return "color:#ffb0c8;font-weight:600"
    return "color:#888;font-weight:600"

styled = filtered.style.map(_style_eligibilite, subset=["Eligibilite"]).format(fmt)
st.dataframe(styled, use_container_width=True, height=440)

st.divider()

# ─────────────────────────────────────────────
#  EXPORT
# ─────────────────────────────────────────────
st.markdown("### Exporter")

ex1, ex2 = st.columns(2)

with ex1:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as wr:
        results.to_excel(wr, index=True, sheet_name="Resultats")
    st.download_button(
        "Télécharger (Excel)",
        data=buf.getvalue(),
        file_name="resultats_orientation.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with ex2:
    # ✅ Générer et télécharger PDF
    pdf_data = generate_pdf_report(results, matieres_detectees, classe)
    
    st.download_button(
        "Télécharger (PDF)",
        data=pdf_data,
        file_name="resultats_orientation.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
