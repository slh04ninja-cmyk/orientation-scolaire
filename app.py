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

st.set_page_config(
    page_title="Orientation Scolaire",
    page_icon="\U0001F393",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("<style>" + get_css() + "</style>", unsafe_allow_html=True)
st.markdown(html_header(), unsafe_allow_html=True)


# ✅ FONCTION GÉNÉRATION PDF
def generate_pdf_report(results_df, matieres_list, classe):
    """Génère un rapport PDF avec les résultats d'orientation"""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    
    buffer = BytesIO()
    
    # Créer le PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor("#7c6cf0"),
        spaceAfter=12,
        alignment=1
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor("#333333"),
        spaceAfter=8,
    )
    
    # Titre
    title = Paragraph("📚 Rapport d'Orientation Scolaire", title_style)
    story.append(title)
    story.append(Spacer(1, 0.2*inch))
    
    # Info classe et matières
    matieres_text = ", ".join(matieres_list) if isinstance(matieres_list, list) else str(matieres_list)
    info = Paragraph(f"<b>Classe:</b> {classe} | <b>Matières:</b> {matieres_text}", heading_style)
    story.append(info)
    story.append(Spacer(1, 0.15*inch))
    
    # Préparer données table
    table_data = [["Rang", "Élève", "Score", "Filière", "Éligibilité"]]
    
    for idx, row in results_df.head(30).iterrows():
        table_data.append([
            str(idx),
            str(row.get("Eleve", ""))[:30],
            f"{row.get('Score', 0):.1f}",
            str(row.get("Filiere principale", "---")),
            str(row.get("Eligibilite", ""))[:40]
        ])
    
    # Créer table
    table = Table(table_data, colWidths=[0.6*inch, 1.8*inch, 0.8*inch, 0.8*inch, 1.6*inch])
    
    # Style table
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#7c6cf0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 0.2*inch))
    
    # Statistiques
    stats = f"<b>Statistiques:</b> Total: {len(results_df)} élèves | Score moyen: {results_df['Score'].mean():.1f}/100"
    story.append(Paragraph(stats, heading_style))
    
    # Générer PDF
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
    df_merged, matieres_detectees, classe, devoirs_par_matiere = process_multiple_files(uploaded_files)
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
    # Score moyen sera ajouté après calcul

st.divider()

# ─────────────────────────────────────────────
#  CALCUL DES SCORES
# ─────────────────────────────────────────────
# Séparer les noms et les moyennes
student_names = df_merged["Eleve"]
averages = df_merged.drop(columns=["Eleve"]).set_index(df_merged["Eleve"])

scores = compute_student_score(averages, WEIGHTS)

# Mise à jour de la colonne info_col3 avec le score moyen
with info_col3:
    st.markdown(f"- **Score moyen :** {scores.mean():.1f} / 100")

results = classify_all(student_names, averages, scores, THRESHOLDS)

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
