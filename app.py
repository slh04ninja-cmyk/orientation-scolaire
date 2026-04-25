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
    style_primary,
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
#  CSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }

.stApp { background: #0e0e1a; color: #e0e0e0; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b0b18 0%, #151530 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}

.block-container { padding-top: 2rem; max-width: 1200px; }

.metric-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 18px;
    padding: 1.6rem 1.4rem;
    backdrop-filter: blur(12px);
    transition: transform .3s ease, box-shadow .3s ease;
}
.metric-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 14px 44px rgba(0,0,0,.35);
}

.track-badge {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 30px;
    font-weight: 600;
    font-size: .8rem;
    margin: 2px;
}

[data-testid="stFileUploadDropzone"] {
    border: 2px dashed rgba(255,255,255,0.12) !important;
    border-radius: 16px !important;
}

[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; }

hr { border-color: rgba(255,255,255,0.06) !important; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 6px; }
</style>
""",
    unsafe_allow_html=True,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HEADER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown(
    """
<div style="text-align:center;padding:.6rem 0 1.8rem">
  <h1 style="font-size:2.4rem;margin-bottom:.3rem;
      background:linear-gradient(135deg,#7c6cf0,#22c997,#f06292);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
      background-clip:text;">
    Système d'Orientation Scolaire
  </h1>
  <p style="color:rgba(255,255,255,.55);font-size:1.05rem;max-width:700px;margin:auto">
    Score par filière → Seuils →
    <b style="color:#7c6cf0">SM</b> ·
    <b style="color:#22c997">SE</b> ·
    <b style="color:#f06292">LT</b>
  </p>
</div>
""",
    unsafe_allow_html=True,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SIDEBAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.divider()

    uploaded_file = st.file_uploader(
        "📁 Importer le fichier Excel",
        type=["xlsx", "xls", "csv"],
        help="Colonnes : Nom, Prénom, puis notes par matière (2-4 devoirs).",
    )

    # ── Pondérations PAR FILIÈRE ──────────────────────────────────
    st.divider()
    st.markdown("#### ⚖️ Poids des matières par filière")
    st.caption("Chaque filière favorise ses propres matières dans son score.")

    def _w(label: str, default: float, key: str) -> float:
        return st.slider(label, 0.0, 5.0, default, 0.5, key=key)

    # ── SM ──
    st.markdown("**🟣 Sciences Mathématiques**")
    st.caption("Favorise fortement les Mathématiques")
    sm_m = _w("Mathématiques", 5.0, "sm_m")
    sm_p = _w("Physique",      3.0, "sm_p")
    sm_s = _w("SVT",           1.0, "sm_s")
    sm_f = _w("Français",      1.0, "sm_f")

    # ── SE ──
    st.markdown("**🟢 Sciences Expérimentales**")
    st.caption("Favorise la SVT et la Physique")
    se_m = _w("Mathématiques", 2.0, "se_m")
    se_p = _w("Physique",      3.0, "se_p")
    se_s = _w("SVT",           4.0, "se_s")
    se_f = _w("Français",      1.0, "se_f")

    # ── LT ──
    st.markdown("**🔴 Lettres & Traduction**")
    st.caption("Favorise fortement le Français")
    lt_m = _w("Mathématiques", 1.0, "lt_m")
    lt_p = _w("Physique",      1.0, "lt_p")
    lt_s = _w("SVT",           1.0, "lt_s")
    lt_f = _w("Français",      5.0, "lt_f")

    TRACK_WEIGHTS = {
        "SM": {"Mathématiques": sm_m, "Physique": sm_p, "SVT": sm_s, "Français": sm_f},
        "SE": {"Mathématiques": se_m, "Physique": se_p, "SVT": se_s, "Français": se_f},
        "LT": {"Mathématiques": lt_m, "Physique": lt_p, "SVT": lt_s, "Français": lt_f},
    }

    # ── Résumé visuel des poids ──
    with st.expander("📊 Résumé des poids"):
        weights_df = pd.DataFrame(TRACK_WEIGHTS).T
        weights_df.index.name = "Filière"
        st.dataframe(weights_df, use_container_width=True)

    # ── Seuils ──
    st.divider()
    st.markdown("#### 🎯 Seuils d'éligibilité")
    st.caption(
        "Score minimum PAR FILIÈRE pour y accéder. "
        "Un élève peut être éligible à plusieurs filières."
    )

    seuil_sm = st.slider("Seuil SM", 0, 100, DEFAULT_THRESHOLDS["SM"], 1, key="s_sm")
    seuil_se = st.slider("Seuil SE", 0, 100, DEFAULT_THRESHOLDS["SE"], 1, key="s_se")
    seuil_lt = st.slider("Seuil LT", 0, 100, DEFAULT_THRESHOLDS["LT"], 1, key="s_lt")

    THRESHOLDS = {"SM": seuil_sm, "SE": seuil_se, "LT": seuil_lt}

    if not (seuil_sm >= seuil_se >= seuil_lt):
        st.warning("⚠️ Les seuils doivent être SM ≥ SE ≥ LT")

    # ── Échelle visuelle ──
    st.markdown(
        f"""
<div style="margin-top:.8rem;padding:.8rem 1rem;
     background:rgba(255,255,255,.03);border-radius:12px;
     border:1px solid rgba(255,255,255,.06);font-size:.85rem">
  <div style="color:rgba(255,255,255,.5);margin-bottom:.5rem">
    Échelle des seuils
  </div>
  <div style="position:relative;height:30px;margin:8px 0">
    <div style="position:absolute;top:12px;left:0;right:0;height:6px;
         background:linear-gradient(90deg,#f06292,#22c997,#7c6cf0);
         border-radius:6px"></div>
    <div style="position:absolute;top:6px;left:{seuil_lt}%;
         width:18px;height:18px;border-radius:50%;
         background:#f06292;border:2px solid #0e0e1a;
         transform:translateX(-50%)"></div>
    <div style="position:absolute;top:6px;left:{seuil_se}%;
         width:18px;height:18px;border-radius:50%;
         background:#22c997;border:2px solid #0e0e1a;
         transform:translateX(-50%)"></div>
    <div style="position:absolute;top:6px;left:{seuil_sm}%;
         width:18px;height:18px;border-radius:50%;
         background:#7c6cf0;border:2px solid #0e0e1a;
         transform:translateX(-50%)"></div>
  </div>
  <div style="display:flex;justify-content:space-between;
       color:rgba(255,255,255,.4);font-size:.75rem">
    <span>0</span>
    <span style="color:#f06292">LT ≥{seuil_lt}</span>
    <span style="color:#22c997">SE ≥{seuil_se}</span>
    <span style="color:#7c6cf0">SM ≥{seuil_sm}</span>
    <span>100</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # ── Aide ──
    st.divider()
    with st.expander("ℹ️ Comment ça marche"):
        st.markdown(
            """
**1. Score PAR FILIÈRE** (chaque filière a ses propres poids) :

