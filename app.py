"""
app.py — Interface Streamlit pour le système d'orientation scolaire.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

from utils import (
    TRACK_ORDER,
    TRACK_NAMES,
    TRACK_COLORS,
    DEFAULT_TRACK_WEIGHTS,
    DEFAULT_THRESHOLDS,
    read_excel_safe,
    clean_dataframe,
    detect_subject_columns,
    build_student_name,
    compute_averages,
    compute_all_scores,
    classify_all,
    load_css,
    build_seuil_html,
    build_stat_card,
    build_student_card,
    build_score_row,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="Orientation Scolaire",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CSS (fichier externe)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown(load_css(), unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HEADER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown(
    '<div style="text-align:center;padding:.6rem 0 1.8rem">'
    '<h1 class="header-title">Systeme d\'Orientation Scolaire</h1>'
    '<p class="header-subtitle">'
    "Score par filiere, seuils et eligibilite multiple : "
    '<b class="color-sm">SM</b> &middot; '
    '<b class="color-se">SE</b> &middot; '
    '<b class="color-lt">LT</b>'
    "</p>"
    "</div>",
    unsafe_allow_html=True,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SIDEBAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.markdown("### Configuration")
    st.divider()

    uploaded_file = st.file_uploader(
        "Importer le fichier Excel",
        type=["xlsx", "xls", "csv"],
        help="Colonnes : Nom, Prenom, puis notes par matiere (2-4 devoirs).",
    )

    # --- Ponderations par filiere ---
    st.divider()
    st.markdown("#### Poids des matieres par filiere")
    st.caption("Chaque filiere favorise ses propres matieres.")

    def _w(label, default, key):
        return st.slider(label, 0.0, 5.0, default, 0.5, key=key)

    st.markdown("**SM - Sciences Mathematiques**")
    st.caption("Favorise fortement les Mathematiques")
    sm_m = _w("Mathematiques", 5.0, "sm_m")
    sm_p = _w("Physique",      3.0, "sm_p")
    sm_s = _w("SVT",           1.0, "sm_s")
    sm_f = _w("Francais",      1.0, "sm_f")

    st.markdown("**SE - Sciences Experimentales**")
    st.caption("Favorise la SVT et la Physique")
    se_m = _w("Mathematiques", 2.0, "se_m")
    se_p = _w("Physique",      3.0, "se_p")
    se_s = _w("SVT",           4.0, "se_s")
    se_f = _w("Francais",      1.0, "se_f")

    st.markdown("**LT - Lettres et Traduction**")
    st.caption("Favorise fortement le Francais")
    lt_m = _w("Mathematiques", 1.0, "lt_m")
    lt_p = _w("Physique",      1.0, "lt_p")
    lt_s = _w("SVT",           1.0, "lt_s")
    lt_f = _w("Francais",      5.0, "lt_f")

    TRACK_WEIGHTS = {
        "SM": {"Mathématiques": sm_m, "Physique": sm_p, "SVT": sm_s, "Français": sm_f},
        "SE": {"Mathématiques": se_m, "Physique": se_p, "SVT": se_s, "Français": se_f},
        "LT": {"Mathématiques": lt_m, "Physique": lt_p, "SVT": lt_s, "Français": lt_f},
    }

    with st.expander("Resume des poids"):
        weights_df = pd.DataFrame(TRACK_WEIGHTS).T
        weights_df.index.name = "Filiere"
        st.dataframe(weights_df, use_container_width=True)

    # --- Seuils ---
    st.divider()
    st.markdown("#### Seuils d'eligibilite")
    st.caption(
        "Score minimum par filiere. "
        "Un eleve peut etre eligible a plusieurs filieres."
    )

    seuil_sm = st.slider("Seuil SM", 0, 100, DEFAULT_THRESHOLDS["SM"], 1, key="s_sm")
    seuil_se = st.slider("Seuil SE", 0, 100, DEFAULT_THRESHOLDS["SE"], 1, key="s_se")
    seuil_lt = st.slider("Seuil LT", 0, 100, DEFAULT_THRESHOLDS["LT"], 1, key="s_lt")

    THRESHOLDS = {"SM": seuil_sm, "SE": seuil_se, "LT": seuil_lt}

    if not (seuil_sm >= seuil_se >= seuil_lt):
        st.warning("Les seuils doivent etre SM >= SE >= LT")

    st.markdown(build_seuil_html(seuil_sm, seuil_se, seuil_lt), unsafe_allow_html=True)

    # --- Aide ---
    st.divider()
    with st.expander("Comment ca marche"):
        st.markdown(
            """
**1. Score PAR FILIERE** (chaque filiere a ses propres poids) :

