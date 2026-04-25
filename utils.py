"""
utils.py — Fonctions métier et constantes pour le système d'orientation.
"""

import pandas as pd
import numpy as np

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONSTANTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

TRACK_ORDER = ["SM", "SE", "LT"]

TRACK_NAMES = {
    "SM": "Sciences Mathématiques",
    "SE": "Sciences Expérimentales",
    "LT": "Lettres & Traduction",
}

TRACK_COLORS = {
    "SM": "#7c6cf0",
    "SE": "#22c997",
    "LT": "#f06292",
}

DEFAULT_TRACK_WEIGHTS = {
    "SM": {"Mathématiques": 5.0, "Physique": 3.0, "SVT": 1.0, "Français": 1.0},
    "SE": {"Mathématiques": 2.0, "Physique": 3.0, "SVT": 4.0, "Français": 1.0},
    "LT": {"Mathématiques": 1.0, "Physique": 1.0, "SVT": 1.0, "Français": 5.0},
}

DEFAULT_THRESHOLDS = {
    "SM": 70,
    "SE": 50,
    "LT": 30,
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LECTURE EXCEL MULTI-MOTEUR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def read_excel_safe(uploaded_file) -> pd.DataFrame:
    errors = []

    for engine in ("calamine", "openpyxl", "xlrd"):
        try:
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file, engine=engine)
        except Exception as e:
            errors.append(f"{engine} : {e}")

    for sep in ("\t", ";", ","):
        try:
            uploaded_file.seek(0)
            raw = uploaded_file.read().decode("utf-8", errors="replace")
            df = pd.read_csv(pd.io.common.StringIO(raw), sep=sep)
            if len(df.columns) > 1:
                return df
        except Exception as e:
            errors.append(f"csv/{repr(sep)} : {e}")

    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read().decode("utf-8", errors="replace")
        df = pd.read_csv(pd.io.common.StringIO(raw), sep=None, engine="python")
        if len(df.columns) > 1:
            return df
    except Exception as e:
        errors.append(f"csv/auto : {e}")

    raise RuntimeError(
        "Aucun moteur n'a pu lire le fichier.\n\n"
        + "\n".join(f"  - {e}" for e in errors)
        + "\n\nConseil : ouvrez le fichier dans Excel, "
          "Enregistrer sous .xlsx, puis réimportez."
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  NETTOYAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df = df.dropna(how="all")
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DETECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_subject_columns(df: pd.DataFrame) -> dict:
    mapping = {}
    for col in df.columns:
        low = col.lower().strip()
        for subject, keywords in SUBJECT_PATTERNS.items():
            if any(kw in low for kw in keywords):
                mapping.setdefault(subject, []).append(col)
                break
    return mapping


def detect_student_columns(df: pd.DataFrame):
    nom = prenom = complet = None
    for col in df.columns:
        low = col.lower().strip()
        if any(k in low for k in (
            "nom et prénom", "nom et prenom", "nom_complet",
            "nom complet", "élève", "eleve",
        )):
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
    return pd.Series(
        [f"Eleve {i+1}" for i in range(len(df))],
        index=df.index,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALCULS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_averages(df: pd.DataFrame, subject_cols: dict) -> pd.DataFrame:
    avgs = pd.DataFrame(index=df.index)
    for subject, cols in subject_cols.items():
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        avgs[subject] = df[cols].mean(axis=1).round(2)
    return avgs.fillna(0)


def compute_track_score(
    averages: pd.DataFrame,
    track_weights: dict,
) -> pd.Series:
    total_weight = sum(track_weights.get(s, 0) for s in averages.columns)
    if total_weight == 0:
        return pd.Series(0.0, index=averages.index)

    score = pd.Series(0.0, index=averages.index)
    for subject in averages.columns:
        w = track_weights.get(subject, 0)
        score += w * averages[subject]

    return ((score / total_weight) * 5).round(2)


def compute_all_scores(
    averages: pd.DataFrame,
    all_track_weights: dict,
) -> pd.DataFrame:
    scores_df = pd.DataFrame(index=averages.index)
    for track, weights in all_track_weights.items():
        scores_df[track] = compute_track_score(averages, weights)
    scores_df["Score_Global"] = scores_df[TRACK_ORDER].max(axis=1)
    return scores_df


def classify_all(
    student_names: pd.Series,
    averages: pd.DataFrame,
    scores_df: pd.DataFrame,
    thresholds: dict,
) -> pd.DataFrame:
    rows = []
    for idx in range(len(averages)):
        row = {"Eleve": student_names.iloc[idx]}

        for track in TRACK_ORDER:
            row[f"Score {track}"] = scores_df[track].iloc[idx]

        row["Score_Global"] = scores_df["Score_Global"].iloc[idx]

        eligible = []
        for track in TRACK_ORDER:
            if row[f"Score {track}"] >= thresholds.get(track, 0):
                eligible.append(track)

        row["Filiere principale"] = eligible[0] if eligible else "---"
        row["Eligibilite"] = " | ".join(eligible) if eligible else "Aucune"
        row["Nb filieres"] = len(eligible)

        for subj in averages.columns:
            row[f"Moy. {subj}"] = averages.iloc[idx].get(subj, 0)

        rows.append(row)

    result = pd.DataFrame(rows)
    result = result.sort_values(
        "Score_Global", ascending=False
    ).reset_index(drop=True)
    result.index = result.index + 1
    result.index.name = "Rang"
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CHARGEMENT CSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_css(path: str = "style.css"):
    """Charge un fichier CSS externe et l'injecte dans Streamlit."""
    import os
    css_path = os.path.join(os.path.dirname(__file__), path)
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    return f"<style>\n{css}\n</style>"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONSTRUCTION HTML (pour eviter les triple-quotes dans app.py)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_seuil_html(seuil_sm: int, seuil_se: int, seuil_lt: int) -> str:
    return (
        '<div class="seuil-container">'
        '<div style="color:rgba(255,255,255,.5);margin-bottom:.5rem">'
        "Echelle des seuils"
        "</div>"
        '<div class="seuil-track">'
        '<div class="seuil-bar"></div>'
        '<div class="seuil-marker" style="left:' + str(seuil_lt) + '%;background:#f06292"></div>'
        '<div class="seuil-marker" style="left:' + str(seuil_se) + '%;background:#22c997"></div>'
        '<div class="seuil-marker" style="left:' + str(seuil_sm) + '%;background:#7c6cf0"></div>'
        "</div>"
        '<div class="seuil-labels">'
        "<span>0</span>"
        '<span class="color-lt">LT &ge;' + str(seuil_lt) + "</span>"
        '<span class="color-se">SE &ge;' + str(seuil_se) + "</span>"
        '<span class="color-sm">SM &ge;' + str(seuil_sm) + "</span>"
        "<span>100</span>"
        "</div>"
        "</div>"
    )


def build_stat_card(count: int, color: str, subtitle: str, pct: str) -> str:
    return (
        '<div class="metric-card" style="border-left:4px solid ' + color + '">'
        '<div style="color:' + color + ';font-size:2rem;font-weight:700">'
        + str(count) + "</div>"
        '<div style="color:rgba(255,255,255,.7);font-size:.85rem">'
        + subtitle + "</div>"
        '<div style="color:rgba(255,255,255,.35);font-size:.8rem">'
        + pct + "</div>"
        "</div>"
    )


def build_student_card(name: str, score: float, primary: str, pname: str, pcol: str) -> str:
    return (
        '<div class="metric-card student-card">'
        '<h3 class="student-name">' + name + "</h3>"
        '<div class="student-score" style="color:' + pcol + '">'
        + f"{score:.1f}"
        + '<span class="student-score-unit">/100</span>'
        "</div>"
        '<div style="margin-top:.8rem">'
        '<span class="track-badge" style="background:' + pcol + '22;color:' + pcol
        + ";border:2px solid " + pcol + '">'
        "Recommandation : " + primary + " - " + pname
        "</span>"
        "</div>"
        "</div>"
    )


def build_score_row(track: str, name: str, score: float, threshold: int,
                     color: str, eligible: bool) -> str:
    css_class = "eligible" if eligible else "not-eligible"
    icon = "OK" if eligible else "NON"
    pct = min(score, 100)

    return (
        '<div class="score-row ' + css_class + '">'
        '<div style="display:flex;justify-content:space-between;'
        'align-items:center;margin-bottom:6px">'
        "<span>"
        '<span style="font-size:1rem">' + icon + "</span>"
        '<span class="score-label" style="color:' + color + '">'
        + track + " - " + name + "</span>"
        "</span>"
        '<span class="score-value">'
        + f"{score:.1f}"
        + ' <span class="score-threshold">/ seuil ' + str(threshold) + "</span>"
        "</span>"
        "</div>"
        '<div class="progress-bar-bg">'
        '<div class="progress-bar-fill" style="background:' + color
        + ";width:" + f"{pct}" + '%"></div>'
        "</div>"
        "</div>"
              )
              
