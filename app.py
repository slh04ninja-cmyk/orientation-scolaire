import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import os

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

st.set_page_config(...)  # inchangé
st.markdown("<style>" + get_css() + "</style>", unsafe_allow_html=True)
st.markdown(html_header(), unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SIDEBAR
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

# ── PAGE D'ACCUEIL ──
if not uploaded_files:
    st.markdown(html_welcome(), unsafe_allow_html=True)
    st.markdown("### Exemple de format attendu")
    # ... (exemple inchangé)
    st.stop()

# ─────────────────────────────────────────────
# TRAITEMENT DES FICHIERS
# ─────────────────────────────────────────────
try:
    df_merged, matieres_detectees, classe, devoirs_par_matiere = process_multiple_files(uploaded_files)
except Exception as exc:
    st.error("Erreur lors du traitement des fichiers : " + str(exc))
    st.stop()

# ── Poids dynamiques par matière ──
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

    # ── Seuils (inchangés) ──
    st.markdown("#### Seuils d'éligibilité")
    col_sm, col_se, col_lt = st.columns(3)
    with col_sm:
        seuil_sm = st.number_input("SM", ..., key="s_sm")
    with col_se:
        seuil_se = st.number_input("SE", ..., key="s_se")
    with col_lt:
        seuil_lt = st.number_input("LT", ..., key="s_lt")
    THRESHOLDS = {"SM": seuil_sm, "SE": seuil_se, "LT": seuil_lt}
    st.markdown(html_seuil_scale(seuil_sm, seuil_se, seuil_lt), unsafe_allow_html=True)

    st.divider()
    with st.expander("Comment ça marche"):
        st.markdown(help_text())

# ─────────────────────────────────────────────
# DÉTECTION AUTOMATIQUE
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
    # Score moyen temporaire (calculé plus tard, on peut l'afficher après)
    # On le mettra après le calcul du score
st.divider()

# ─────────────────────────────────────────────
# CALCUL DES SCORES
# ─────────────────────────────────────────────
# df_merged contient Eleve + colonnes des moyennes par matière (déjà /20)
averages = df_merged.set_index("Eleve")  # pour aligner avec compute_averages
student_names = df_merged["Eleve"]
scores = compute_student_score(averages, WEIGHTS)

# Mise à jour de la colonne score moyen
with info_col3:
    st.markdown(f"- **Score moyen :** {scores.mean():.1f} / 100")

# Classification
results = classify_all(student_names, averages, scores, THRESHOLDS)

# ── STATISTIQUES (inchangé) ──
# ...

# ── TABLEAU DES RÉSULTATS (inchangé) ──
# ...

# ── EXPORT (inchangé) ──
# ...
