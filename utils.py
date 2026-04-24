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

DEFAULT_WEIGHTS = {
    "SM": {"Mathématiques": 3.0, "Physique": 2.5, "SVT": 1.0, "Français": 0.5},
    "SE": {"Mathématiques": 1.5, "Physique": 2.0, "SVT": 3.0, "Français": 0.5},
    "LT": {"Mathématiques": 0.5, "Physique": 0.5, "SVT": 0.5, "Français": 3.5},
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LECTURE EXCEL MULTI-MOTEUR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def read_excel_safe(uploaded_file) -> pd.DataFrame:
    """
    Essaie plusieurs moteurs de lecture pour tolérer les fichiers
    Excel corrompus (styles XML cassés, encodage, etc.).
    """
    errors = []

    # 1) calamine (Rust — très tolérant aux XML cassés)
    try:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file, engine="calamine")
    except Exception as e:
        errors.append(f"calamine : {e}")

    # 2) openpyxl classique
    try:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file, engine="openpyxl")
    except Exception as e:
        errors.append(f"openpyxl : {e}")

    # 3) xlrd (ancien format .xls)
    try:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file, engine="xlrd")
    except Exception as e:
        errors.append(f"xlrd : {e}")

    # 4) CSV avec tabulation
    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read().decode("utf-8", errors="replace")
        df = pd.read_csv(pd.io.common.StringIO(raw), sep="\t")
        if len(df.columns) > 1:
            return df
    except Exception as e:
        errors.append(f"csv/tab : {e}")

    # 5) CSV avec point-virgule
    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read().decode("utf-8", errors="replace")
        df = pd.read_csv(pd.io.common.StringIO(raw), sep=";")
        if len(df.columns) > 1:
            return df
    except Exception as e:
        errors.append(f"csv/; : {e}")

    # 6) CSV auto-détection
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
        + "\n".join(f"  • {e}" for e in errors)
        + "\n\n💡 Conseil : ouvrez le fichier dans Excel → "
          "Fichier → Enregistrer sous → .xlsx → réimportez."
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DÉTECTION DES COLONNES
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
    """Construit le nom complet de chaque élève à partir des colonnes détectées."""
    nom, prenom, complet = detect_student_columns(df)
    if complet:
        return df[complet].astype(str)
    if nom and prenom:
        return df[nom].astype(str) + " " + df[prenom].astype(str)
    if nom:
        return df[nom].astype(str)
    return pd.Series([f"Élève {i+1}" for i in range(len(df))], index=df.index)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALCULS & CLASSIFICATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_averages(
    df: pd.DataFrame,
    subject_cols: dict[str, list[str]],
) -> pd.DataFrame:
    """Calcule la moyenne par matière pour chaque élève."""
    avgs = pd.DataFrame(index=df.index)
    for subject, cols in subject_cols.items():
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        avgs[subject] = df[cols].mean(axis=1).round(2)
    return avgs.fillna(0)


def classify(
    row: pd.Series,
    weights: dict,
) -> tuple[str, dict, float]:
    """
    Pour un élève (ses moyennes par matière), calcule le score pondéré
    pour chaque filière et renvoie (filière, scores, confiance).
    """
    scores = {}
    for track, tw in weights.items():
        scores[track] = round(
            sum(tw.get(s, 0) * row.get(s, 0) for s in row.index), 2
        )
    best = max(scores, key=scores.get)
    sorted_v = sorted(scores.values(), reverse=True)
    confidence = round(sorted_v[0] - sorted_v[1], 2) if len(sorted_v) > 1 else 0.0
    return best, scores, confidence


def classify_all(
    df: pd.DataFrame,
    averages: pd.DataFrame,
    weights: dict,
    student_names: pd.Series,
) -> pd.DataFrame:
    """Classifie tous les élèves et renvoie un DataFrame de résultats."""
    rows = []
    for idx in range(len(df)):
        avgs = averages.iloc[idx]
        filiere, scores, conf = classify(avgs, weights)
        row = {
            "Élève": student_names.iloc[idx],
            "Filière": filiere,
            "Score SM": scores["SM"],
            "Score SE": scores["SE"],
            "Score LT": scores["LT"],
            "Confiance": conf,
        }
        for subj in averages.columns:
            row[f"Moy. {subj}"] = avgs.get(subj, 0)
        rows.append(row)
    return pd.DataFrame(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  NETTOYAGE DU DATAFRAME BRUT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime les colonnes Unnamed et les lignes entièrement vides."""
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df = df.dropna(how="all")
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STYLE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def style_filiere(val: str) -> str:
    """Retourne un style CSS inline pour colorer la filière dans un tableau."""
    m = {
        "SM": "background:rgba(124,108,240,.18);color:#b8b0ff;font-weight:600",
        "SE": "background:rgba(34,201,151,.15);color:#7aebc8;font-weight:600",
        "LT": "background:rgba(240,98,146,.15);color:#ffb0c8;font-weight:600",
    }
    return m.get(val, "")
      
