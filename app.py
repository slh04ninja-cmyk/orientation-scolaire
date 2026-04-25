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
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")
    st.divider()

    uploaded_file = st.file_uploader(
        "Importer le fichier Excel",
        type=["xlsx", "xls", "csv"],
    )

    st.divider()

    # ── Poids des matières (un seul jeu commun) ──
    st.markdown("#### Poids des matieres")
    st.caption("Ces poids s'appliquent à toutes les filieres pour calculer le score unique.")

    def _w(label, default, key):
        return st.slider(label, 0.0, 5.0, default, 0.5, key=key)

    w_math = _w("Mathematiques", DEFAULT_WEIGHTS["Mathematiques"], "w_math")
    w_phys = _w("Physique",       DEFAULT_WEIGHTS["Physique"],       "w_phys")
    w_svt  = _w("SVT",            DEFAULT_WEIGHTS["SVT"],            "w_svt")
    w_fr   = _w("Francais",       DEFAULT_WEIGHTS["Francais"],       "w_fr")

    WEIGHTS = {
        "Mathematiques": w_math,
        "Physique":      w_phys,
        "SVT":           w_svt,
        "Francais":      w_fr,
    }

    total_w = sum(WEIGHTS.values())
    if total_w == 0:
        st.error("Les poids ne peuvent pas être tous à zéro.")

    with st.expander("Resume des poids"):
        wdf = pd.DataFrame(
            {"Matiere": list(WEIGHTS.keys()), "Poids": list(WEIGHTS.values())}
        )
        wdf["Part (%)"] = (wdf["Poids"] / total_w * 100).round(1) if total_w > 0 else 0
        st.dataframe(wdf, use_container_width=True, hide_index=True)

    st.divider()

    # ── Seuils d'éligibilité — saisie libre ──
    st.markdown("#### Seuils d'eligibilite")
    st.caption("Entrez le score minimum /100 requis pour chaque filiere.")

    col_sm, col_se, col_lt = st.columns(3)
    with col_sm:
        seuil_sm = st.number_input(
            "SM", min_value=0, max_value=100,
            value=DEFAULT_THRESHOLDS["SM"], step=1, key="s_sm",
            help="Score minimum pour Sciences Mathematiques"
        )
    with col_se:
        seuil_se = st.number_input(
            "SE", min_value=0, max_value=100,
            value=DEFAULT_THRESHOLDS["SE"], step=1, key="s_se",
            help="Score minimum pour Sciences Experimentales"
        )
    with col_lt:
        seuil_lt = st.number_input(
            "LT", min_value=0, max_value=100,
            value=DEFAULT_THRESHOLDS["LT"], step=1, key="s_lt",
            help="Score minimum pour Lettres et Traduction"
        )

    THRESHOLDS = {"SM": seuil_sm, "SE": seuil_se, "LT": seuil_lt}

    if not (seuil_sm > seuil_se > seuil_lt):
        st.warning("Recommande : SM > SE > LT pour une orientation discriminante.")

    st.markdown(html_seuil_scale(seuil_sm, seuil_se, seuil_lt), unsafe_allow_html=True)

    st.divider()
    with st.expander("Comment ca marche"):
        st.markdown(help_text())


# ─────────────────────────────────────────────
# PAGE D'ACCUEIL — aucun fichier uploadé
# ─────────────────────────────────────────────
if uploaded_file is None:
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
# LECTURE & TRAITEMENT
# ─────────────────────────────────────────────
try:
    df_raw = read_excel_safe(uploaded_file)
except Exception as exc:
    st.error("Impossible de lire le fichier : " + str(exc))
    st.stop()

df_raw = clean_dataframe(df_raw)

subject_cols = detect_subject_columns(df_raw)
if not subject_cols:
    st.error("Aucune matiere reconnue. Verifiez vos colonnes.")
    st.code(", ".join(str(c) for c in df_raw.columns))
    st.stop()

student_names = build_student_name(df_raw)
averages      = compute_averages(df_raw.copy(), subject_cols)
scores        = compute_student_score(averages, WEIGHTS)
results       = classify_all(student_names, averages, scores, THRESHOLDS)


# ─────────────────────────────────────────────
# DETECTION AUTOMATIQUE
# ─────────────────────────────────────────────
st.markdown("### Detection automatique")
c1, c2 = st.columns(2)
with c1:
    for subj, cols in subject_cols.items():
        st.markdown(
            "- **" + subj + "** — " + str(len(cols)) + " devoir(s) : `" + ", ".join(cols) + "`"
        )
with c2:
    st.markdown("- **Eleves detectes :** " + str(len(df_raw)))
    st.markdown("- **Matieres detectees :** " + str(len(subject_cols)))
    st.markdown("- **Score moyen classe :** " + f"{scores.mean():.1f}" + " / 100")

st.divider()


# ─────────────────────────────────────────────
# STATISTIQUES — 3 cartes SM / SE / LT uniquement
# ─────────────────────────────────────────────
st.markdown("### Statistiques")

total    = len(results)
count_sm = int(results["Eligibilite"].str.contains("SM", na=False).sum())
count_se = int(results["Eligibilite"].str.contains("SE", na=False).sum())
count_lt = int(results["Eligibilite"].str.contains("LT", na=False).sum())

stat_items = [
    (count_sm, "#7c6cf0", "Eligibles SM (≥" + str(seuil_sm) + ")"),
    (count_se, "#22c997", "Eligibles SE (≥" + str(seuil_se) + ")"),
    (count_lt, "#f06292", "Eligibles LT (≥" + str(seuil_lt) + ")"),
]

cols_cards = st.columns(3)
for col, (count, color, subtitle) in zip(cols_cards, stat_items):
    pct = str(round(count / total * 100, 1)) + " %" if total else "---"
    with col:
        st.markdown(html_stat_card(count, color, subtitle, pct), unsafe_allow_html=True)

st.divider()


# ─────────────────────────────────────────────
# TABLEAU RÉSULTATS
# Colonnes affichées : Eleve, Score, Eligibilite, Moy. par matière
# Colonnes supprimées : Filiere principale, Nb filieres
# ─────────────────────────────────────────────
st.markdown("### Resultats detailles (tries par score)")

filtre = st.multiselect(
    "Filtrer par eligibilite",
    ["SM", "SE", "LT", "Aucune"],
    default=["SM", "SE", "LT", "Aucune"],
)

# Filtrage
def _match_filtre(row):
    if row["Eligibilite"] == "Aucune":
        return "Aucune" in filtre
    return any(f in row["Eligibilite"] for f in filtre)

filtered = results[results.apply(_match_filtre, axis=1)].copy()

# Supprimer les colonnes non souhaitées
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
# EXPORT
# ─────────────────────────────────────────────
st.markdown("### Exporter")

ex1, ex2 = st.columns(2)

with ex1:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as wr:
        results.to_excel(wr, index=True, sheet_name="Resultats")
    st.download_button(
        "Telecharger (Excel)",
        data=buf.getvalue(),
        file_name="resultats_orientation.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with ex2:
    st.download_button(
        "Telecharger (CSV)",
        data=results.to_csv(index=True).encode("utf-8"),
        file_name="resultats_orientation.csv",
        mime="text/csv",
        use_container_width=True,
    )
