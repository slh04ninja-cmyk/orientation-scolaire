import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="Orientation Scolaire",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

SUBJECT_PATTERNS = {
    "Mathématiques": [
        "mathématiques", "mathematiques", "maths", "math", "mathe",
    ],
    "Physique": [
        "physique", "phys", "chimie", "physique-chimie", "physique chimie",
    ],
    "SVT": [
        "svt", "sciences de la vie", "science de la vie", "biologie",
        "sciences de la vie et de la terre",
    ],
    "Français": [
        "français", "francais", "franç", "langue française",
        "langue francaise", "lf",
    ],
}

TRACK_NAMES = {
    "SM": "Sciences Mathématiques",
    "SE": "Sciences Expérimentales",
    "LT": "Lettres & Traduction",
}

TRACK_COLORS = {"SM": "#7c6cf0", "SE": "#22c997", "LT": "#f06292"}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }

.stApp {
    background: #0e0e1a;
    color: #e0e0e0;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b0b18 0%, #151530 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}

.block-container { padding-top: 2rem; max-width: 1200px; }

/* ── Cards ── */
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

/* ── Track label ── */
.track-badge {
    display: inline-block;
    padding: 6px 18px;
    border-radius: 30px;
    font-weight: 600;
    font-size: .85rem;
    letter-spacing: .04em;
}

/* ── Upload zone ── */
[data-testid="stFileUploadDropzone"] {
    border: 2px dashed rgba(255,255,255,0.12) !important;
    border-radius: 16px !important;
}

/* ── Tables ── */
[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; }

/* ── Dividers ── */
hr { border-color: rgba(255,255,255,0.06) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 6px; }
</style>
""",
    unsafe_allow_html=True,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FONCTIONS UTILITAIRES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_subject_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    """Regroupe les colonnes du DataFrame par matière grâce à des mots-clés."""
    mapping: dict[str, list[str]] = {}
    for col in df.columns:
        low = col.lower().strip()
        for subject, keywords in SUBJECT_PATTERNS.items():
            if any(kw in low for kw in keywords):
                mapping.setdefault(subject, []).append(col)
                break
    return mapping


def detect_student_columns(df: pd.DataFrame):
    """Retourne (col_nom, col_prenom, col_complet) — chacun peut être None."""
    nom = prenom = complet = None
    for col in df.columns:
        low = col.lower().strip()
        if any(k in low for k in ("nom et prénom", "nom et prenom", "nom_complet", "nom complet", "élève", "eleve")):
            complet = col
        elif any(k in low for k in ("prénom", "prenom", "first name")):
            prenom = col
        elif any(k in low for k in ("nom", "name", "last name", "famille")):
            nom = col
    return nom, prenom, complet


def build_student_name(df: pd.DataFrame) -> pd.Series:
    nom, prenom, complet = detect_student_columns(df)
    if complet:
        return df[complet].astype(str)
    if nom and prenom:
        return df[nom].astype(str) + " " + df[prenom].astype(str)
    if nom:
        return df[nom].astype(str)
    return pd.Series([f"Élève {i+1}" for i in range(len(df))], index=df.index)


def compute_averages(df: pd.DataFrame, subject_cols: dict[str, list[str]]) -> pd.DataFrame:
    """Moyenne par matière pour chaque élève."""
    avgs = pd.DataFrame(index=df.index)
    for subject, cols in subject_cols.items():
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        avgs[subject] = df[cols].mean(axis=1).round(2)
    return avgs.fillna(0)


def classify(row: pd.Series, weights: dict) -> tuple[str, dict, float]:
    """Renvoie (filière, scores_dict, confiance)."""
    scores = {}
    for track, tw in weights.items():
        scores[track] = round(sum(tw.get(s, 0) * row.get(s, 0) for s in row.index), 2)
    best = max(scores, key=scores.get)
    sorted_v = sorted(scores.values(), reverse=True)
    confidence = round(sorted_v[0] - sorted_v[1], 2) if len(sorted_v) > 1 else 0.0
    return best, scores, confidence


def style_filiere(val: str) -> str:
    m = {
        "SM": "background:rgba(124,108,240,.18);color:#b8b0ff;font-weight:600",
        "SE": "background:rgba(34,201,151,.15);color:#7aebc8;font-weight:600",
        "LT": "background:rgba(240,98,146,.15);color:#ffb0c8;font-weight:600",
    }
    return m.get(val, "")


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
  <p style="color:rgba(255,255,255,.55);font-size:1.05rem;max-width:640px;margin:auto">
    Classification automatique <b style="color:#7c6cf0">SM</b> ·
    <b style="color:#22c997">SE</b> ·
    <b style="color:#f06292">LT</b> à partir des notes Excel
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
        type=["xlsx", "xls"],
        help="Colonnes attendues : Nom, Prénom, puis les notes par matière (2-4 devoirs).",
    )

    st.divider()
    st.markdown("#### ⚖️ Pondérations")
    st.caption("Ajustez le poids de chaque matière pour chaque filière.")

    def _w(label: str, default: float, key: str) -> float:
        return st.slider(label, 0.0, 5.0, default, 0.5, key=key)

    st.markdown("**🟣 Sciences Mathématiques**")
    sm_m = _w("Math", 3.0, "sm_m")
    sm_p = _w("Physique", 2.5, "sm_p")
    sm_s = _w("SVT", 1.0, "sm_s")
    sm_f = _w("Français", 0.5, "sm_f")

    st.markdown("**🟢 Sciences Expérimentales**")
    se_m = _w("Math", 1.5, "se_m")
    se_p = _w("Physique", 2.0, "se_p")
    se_s = _w("SVT", 3.0, "se_s")
    se_f = _w("Français", 0.5, "se_f")

    st.markdown("**🔴 Lettres & Traduction**")
    lt_m = _w("Math", 0.5, "lt_m")
    lt_p = _w("Physique", 0.5, "lt_p")
    lt_s = _w("SVT", 0.5, "lt_s")
    lt_f = _w("Français", 3.5, "lt_f")

    WEIGHTS = {
        "SM": {"Mathématiques": sm_m, "Physique": sm_p, "SVT": sm_s, "Français": sm_f},
        "SE": {"Mathématiques": se_m, "Physique": se_p, "SVT": se_s, "Français": se_f},
        "LT": {"Mathématiques": lt_m, "Physique": lt_p, "SVT": lt_s, "Français": lt_f},
    }

    st.divider()
    with st.expander("ℹ️ Aide — format du fichier"):
        st.markdown(
            """
- **Colonnes** : `Nom`, `Prénom`, puis notes (ex. `Physique_DS1`, `Math_DS2`…)
- Chaque matière : **2 à 4** devoirs
- Notes **numériques** (de préférence sur 20)
- Les noms de colonnes sont détectés **automatiquement**
"""
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONTENU PRINCIPAL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if uploaded_file is None:
    # ── Écran d'accueil ───────────────────────────────────────────
    st.markdown(
        """
<div style="text-align:center;padding:3.5rem 1rem">
  <div style="font-size:4rem;margin-bottom:.8rem">📂</div>
  <h2 style="color:rgba(255,255,255,.75);font-weight:400">
    Importez un fichier Excel pour démarrer
  </h2>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### 📄 Exemple de format attendu")
    st.dataframe(
        pd.DataFrame(
            {
                "Nom": ["Dupont", "Martin", "Bernard"],
                "Prénom": ["Marie", "Ahmed", "Sophie"],
                "Physique_DS1": [14, 12, 8],
                "Physique_DS2": [15, 11, 9],
                "Physique_DS3": [13, 13, 7],
                "Math_DS1": [16, 10, 12],
                "Math_DS2": [17, 11, 11],
                "Math_DS3": [15, 9, 10],
                "SVT_DS1": [10, 15, 13],
                "SVT_DS2": [11, 16, 14],
                "SVT_DS3": [9, 14, 12],
                "Français_DS1": [12, 11, 16],
                "Français_DS2": [11, 10, 17],
                "Français_DS3": [13, 12, 18],
            }
        ),
        use_container_width=True,
    )
    st.stop()

# ── Traitement du fichier ─────────────────────────────────────────
try:
    df_raw = pd.read_excel(uploaded_file)
except Exception as exc:
    st.error(f"Impossible de lire le fichier : {exc}")
    st.stop()

# Détection
subject_cols = detect_subject_columns(df_raw)
if not subject_cols:
    st.error(
        "Aucune matière reconnue. Vérifiez que vos colonnes contiennent "
        "les mots-clés : **math**, **physique**, **svt**, **français**."
    )
    st.code(", ".join(df_raw.columns))
    st.stop()

df_raw["__Élève__"] = build_student_name(df_raw)
averages = compute_averages(df_raw.copy(), subject_cols)

# Classification
rows = []
for idx in range(len(df_raw)):
    avgs = averages.iloc[idx]
    filiere, scores, conf = classify(avgs, WEIGHTS)
    row = {
        "Élève": df_raw["__Élève__"].iloc[idx],
        "Filière": filiere,
        "Score SM": scores["SM"],
        "Score SE": scores["SE"],
        "Score LT": scores["LT"],
        "Confiance": conf,
    }
    for subj in subject_cols:
        row[f"Moy. {subj}"] = avgs.get(subj, 0)
    rows.append(row)

results = pd.DataFrame(rows)

# ── Détection summary ─────────────────────────────────────────────
st.markdown("### 📋 Détection automatique")
c1, c2 = st.columns(2)
with c1:
    for subj, cols in subject_cols.items():
        st.markdown(f"- **{subj}** — {len(cols)} devoir(s) → `{', '.join(cols)}`")
with c2:
    st.markdown(f"- **Élèves détectés :** {len(df_raw)}")
    st.markdown(f"- **Matières détectées :** {len(subject_cols)}")

st.divider()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STATISTIQUES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("### 📊 Statistiques de classification")

n_sm = int((results["Filière"] == "SM").sum())
n_se = int((results["Filière"] == "SE").sum())
n_lt = int((results["Filière"] == "LT").sum())
total = len(results)

cards = [
    ("SM", n_sm, "#7c6cf0", TRACK_NAMES["SM"]),
    ("SE", n_se, "#22c997", TRACK_NAMES["SE"]),
    ("LT", n_lt, "#f06292", TRACK_NAMES["LT"]),
    ("Total", total, "#f0c27f", "Élèves analysés"),
]

cols_cards = st.columns(4)
for col, (label, count, color, subtitle) in zip(cols_cards, cards):
    pct = f"{count / total * 100:.1f} %" if total else "—"
    with col:
        st.markdown(
            f"""
<div class="metric-card" style="border-left:4px solid {color}">
  <div style="color:{color};font-size:2rem;font-weight:700">{count}</div>
  <div style="color:rgba(255,255,255,.7);font-size:.9rem">{subtitle}</div>
  <div style="color:rgba(255,255,255,.35);font-size:.8rem">{pct}</div>
</div>
""",
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GRAPHIQUES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
g1, g2 = st.columns(2)

with g1:
    st.markdown("#### Répartition par filière")
    fig_pie = px.pie(
        values=[n_sm, n_se, n_lt],
        names=["SM", "SE", "LT"],
        color=["SM", "SE", "LT"],
        color_discrete_map=TRACK_COLORS,
        hole=0.48,
    )
    fig_pie.update_traces(
        textfont_size=14,
        textfont_color="white",
        marker=dict(line=dict(color="#0e0e1a", width=2)),
    )
    fig_pie.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white", family="Outfit"),
        height=360,
        margin=dict(t=20, b=20, l=20, r=20),
        legend=dict(font=dict(color="rgba(255,255,255,.8)")),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with g2:
    st.markdown("#### Moyennes par matière & filière")
    moy_cols = [c for c in results.columns if c.startswith("Moy.")]
    melted = results.groupby("Filière")[moy_cols].mean().reset_index().melt(
        id_vars="Filière", var_name="Matière", value_name="Moyenne"
    )
    melted["Matière"] = melted["Matière"].str.replace("Moy. ", "")
    fig_bar = px.bar(
        melted,
        x="Matière",
        y="Moyenne",
        color="Filière",
        barmode="group",
        color_discrete_map=TRACK_COLORS,
    )
    fig_bar.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white", family="Outfit"),
        height=360,
        margin=dict(t=20, b=20, l=20, r=20),
        legend=dict(font=dict(color="rgba(255,255,255,.8)")),
        xaxis=dict(gridcolor="rgba(255,255,255,.08)", tickfont=dict(color="rgba(255,255,255,.8)")),
        yaxis=dict(gridcolor="rgba(255,255,255,.08)", tickfont=dict(color="rgba(255,255,255,.8)"), range=[0, 20]),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TABLEAU DÉTAILLÉ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("### 📝 Résultats détaillés")

filtre = st.multiselect("Filtrer par filière", ["SM", "SE", "LT"], default=["SM", "SE", "LT"])
filtered = results[results["Filière"].isin(filtre)].copy()

fmt = {c: "{:.2f}" for c in filtered.columns if c.startswith("Score") or c.startswith("Moy.") or c == "Confiance"}
styled = filtered.style.map(style_filiere, subset=["Filière"]).format(fmt)
st.dataframe(styled, use_container_width=True, height=420)

st.divider()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FICHE ÉLÈVE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("### 🔍 Fiche élève")

selected = st.selectbox("Choisir un élève", results["Élève"].tolist())

if selected:
    sd = results[results["Élève"] == selected].iloc[0]
    trk = sd["Filière"]
    col_t = TRACK_COLORS[trk]

    d1, d2 = st.columns([1, 1])

    with d1:
        st.markdown(
            f"""
<div class="metric-card" style="text-align:center;padding:2.2rem 1.4rem">
  <h3 style="color:#fff;margin-bottom:.4rem">{selected}</h3>
  <span class="track-badge" style="background:{col_t}22;color:{col_t};
        border:2px solid {col_t};font-size:1.1rem;padding:8px 28px">
    {trk} — {TRACK_NAMES[trk]}
  </span>
  <div style="color:rgba(255,255,255,.45);margin-top:1rem;font-size:.9rem">
    Confiance : {sd['Confiance']:.2f} pts
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown("**Scores par filière :**")
        max_sc = max(sd["Score SM"], sd["Score SE"], sd["Score LT"]) or 1
        for t in ("SM", "SE", "LT"):
            sc = sd[f"Score {t}"]
            pct = sc / max_sc * 100
            c = TRACK_COLORS[t]
            st.markdown(
                f"""
<div style="margin:10px 0">
  <div style="display:flex;justify-content:space-between;margin-bottom:5px">
    <span style="color:{c};font-weight:600">{t} — {TRACK_NAMES[t]}</span>
    <span style="color:rgba(255,255,255,.65)">{sc:.2f}</span>
  </div>
  <div style="background:rgba(255,255,255,.08);border-radius:8px;height:10px">
    <div style="background:{c};width:{pct:.1f}%;height:100%;border-radius:8px;
         transition:width .5s ease"></div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

    with d2:
        idx_student = results[results["Élève"] == selected].index[0]
        stu_avgs = averages.iloc[idx_student]
        cats = list(stu_avgs.index)
        vals = list(stu_avgs.values)

        fig_radar = go.Figure()
        fig_radar.add_trace(
            go.Scatterpolar(
                r=vals + [vals[0]],
                theta=cats + [cats[0]],
                fill="toself",
                name=selected,
                fillcolor=f"{col_t}33",
                line=dict(color=col_t, width=2),
            )
        )
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 20], gridcolor="rgba(255,255,255,.1)", tickfont=dict(color="rgba(255,255,255,.5)")),
                angularaxis=dict(gridcolor="rgba(255,255,255,.1)", tickfont=dict(color="rgba(255,255,255,.8)", size=13)),
                bgcolor="rgba(0,0,0,0)",
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            height=380,
            margin=dict(t=50, b=50, l=60, r=60),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

st.divider()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  EXPORT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("### 💾 Exporter")

ex1, ex2 = st.columns(2)
with ex1:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as wr:
        results.to_excel(wr, index=False, sheet_name="Résultats")
    st.download_button(
        "📥 Télécharger (Excel)",
        data=buf.getvalue(),
        file_name="resultats_orientation.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with ex2:
    st.download_button(
        "📥 Télécharger (CSV)",
        data=results.to_csv(index=False).encode("utf-8"),
        file_name="resultats_orientation.csv",
        mime="text/csv",
        use_container_width=True,
)
  
