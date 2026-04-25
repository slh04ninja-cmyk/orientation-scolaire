"""
utils.py — Fonctions métier et constantes pour le système d'orientation.
"""

import pandas as pd
import numpy as np

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONSTANTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SUBJECT_PATTERNS = {
    "Mathématiques": ["mathématiques", "mathematiques", "maths", "math", "mathe"],
    "Physique":      ["physique", "phys", "chimie", "physique-chimie", "physique chimie"],
    "SVT":           ["svt", "sciences de la vie", "science de la vie", "biologie",
                      "sciences de la vie et de la terre"],
    "Français":      ["français", "francais", "franç", "langue française",
                      "langue francaise", "lf"],
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

# ── Poids PAR FILIÈRE (chaque filière favorise ses matières) ──────
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
        + "\n\nConseil : ouvrez le fichier dans Excel → "
          "Fichier → Enregistrer sous → .xlsx → réimportez."
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  NETTOYAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df = df.dropna(how="all")
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DÉTECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_subject_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
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
    return pd.Series([f"Élève {i+1}" for i in range(len(df))], index=df.index)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALCULS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_averages(
    df: pd.DataFrame,
    subject_cols: dict[str, list[str]],
) -> pd.DataFrame:
    """Moyenne par matière pour chaque élève."""
    avgs = pd.DataFrame(index=df.index)
    for subject, cols in subject_cols.items():
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        avgs[subject] = df[cols].mean(axis=1).round(2)
    return avgs.fillna(0)


def compute_track_score(
    averages: pd.DataFrame,
    track_weights: dict[str, float],
) -> pd.Series:
    """
    Score d'UNE filière pour tous les élèves.
    Formule : score = (Σ poids × moyenne) / (Σ poids) × 5
    Le ×5 convertit /20 en /100.
    """
    total_weight = sum(
        track_weights.get(s, 0) for s in averages.columns
    )
    if total_weight == 0:
        return pd.Series(0.0, index=averages.index)

    score = pd.Series(0.0, index=averages.index)
    for subject in averages.columns:
        w = track_weights.get(subject, 0)
        score += w * averages[subject]

    return ((score / total_weight) * 5).round(2)


def compute_all_scores(
    averages: pd.DataFrame,
    all_track_weights: dict[str, dict[str, float]],
) -> pd.DataFrame:
    """
    Calcule un score PAR FILIÈRE pour chaque élève.
    Colonnes : SM, SE, LT + Score_Global (meilleur des trois).
    """
    scores_df = pd.DataFrame(index=averages.index)
    for track, weights in all_track_weights.items():
        scores_df[track] = compute_track_score(averages, weights)

    scores_df["Score_Global"] = scores_df[TRACK_ORDER].max(axis=1)
    return scores_df


def classify_all(
    student_names: pd.Series,
    averages: pd.DataFrame,
    scores_df: pd.DataFrame,
    thresholds: dict[str, float],
) -> pd.DataFrame:
    """
    Pour chaque élève :
    - Récupère les 3 scores par filière
    - Compare chaque score au seuil de sa filière
    - Attribue les filières éligibles
    - Trie par score global décroissant
    """
    rows = []
    for idx in range(len(averages)):
        row = {
            "Élève": student_names.iloc[idx],
        }

        # Scores par filière
        for track in TRACK_ORDER:
            row[f"Score {track}"] = scores_df[track].iloc[idx]

        row["Score_Global"] = scores_df["Score_Global"].iloc[idx]

        # Éligibilité
        eligible = []
        for track in TRACK_ORDER:
            if row[f"Score {track}"] >= thresholds.get(track, 0):
                eligible.append(track)

        row["Filière principale"] = eligible[0] if eligible else "—"
        row["Éligibilité"] = " | ".join(eligible) if eligible else "Aucune"
        row["Nb filières"] = len(eligible)

        # Moyennes par matière
        for subj in averages.columns:
            row[f"Moy. {subj}"] = averages.iloc[idx].get(subj, 0)

        rows.append(row)

    result = pd.DataFrame(rows)
    result = result.sort_values("Score_Global", ascending=False).reset_index(drop=True)
    result.index = result.index + 1
    result.index.name = "Rang"
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STYLE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def style_primary(val: str) -> str:
    m = {
        "SM": "background:rgba(124,108,240,.18);color:#b8b0ff;font-weight:600",
        "SE": "background:rgba(34,201,151,.15);color:#7aebc8;font-weight:600",
        "LT": "background:rgba(240,98,146,.15);color:#ffb0c8;font-weight:600",
        "—": "background:rgba(255,255,255,.05);color:#888;font-weight:600",
    }
    return m.get(val, "")
    
