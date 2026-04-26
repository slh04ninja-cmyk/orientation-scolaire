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

# Formatage
fmt = {"Score": "{:.2f}"}
for c in filtered.columns:
    if c.startswith("Moy."):
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
    st.download_button(
        "Télécharger (CSV)",
        data=results.to_csv(index=True).encode("utf-8"),
        file_name="resultats_orientation.csv",
        mime="text/csv",
        use_container_width=True,
)
