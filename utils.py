import pandas as pd
import numpy as np
import os

SUBJECT_PATTERNS = {
    "Mathématiques": ["mathématiques", "mathematiques", "maths", "math", "mathe"],
    "Physique": ["physique", "phys", "chimie", "physique-chimie", "physique chimie"],
    "SVT": ["svt", "sciences de la vie", "science de la vie", "biologie",
            "sciences de la vie et de la terre"],
    "Français": ["français", "francais", "franç", "langue française",
                 "langue francaise", "lf"],
}

TRACK_ORDER = ["SM", "SE", "LT"]

TRACK_NAMES = {
    "SM": "Sciences Mathématiques",
    "SE": "Sciences Expérimentales",
    "LT": "Lettres & Traduction",
}

TRACK_COLORS = {"SM": "#7c6cf0", "SE": "#22c997", "LT": "#f06292"}

DEFAULT_TRACK_WEIGHTS = {
    "SM": {"Mathématiques": 5.0, "Physique": 3.0, "SVT": 1.0, "Français": 1.0},
    "SE": {"Mathématiques": 2.0, "Physique": 3.0, "SVT": 4.0, "Français": 1.0},
    "LT": {"Mathématiques": 1.0, "Physique": 1.0, "SVT": 1.0, "Français": 5.0},
}

DEFAULT_THRESHOLDS = {"SM": 70, "SE": 50, "LT": 30}


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
    raise RuntimeError("Aucun moteur n'a pu lire le fichier.\n" + "\n".join(errors))


def clean_dataframe(df):
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df = df.dropna(how="all")
    return df


def detect_subject_columns(df):
    mapping = {}
    for col in df.columns:
        low = col.lower().strip()
        for subject, keywords in SUBJECT_PATTERNS.items():
            if any(kw in low for kw in keywords):
                mapping.setdefault(subject, []).append(col)
                break
    return mapping


def detect_student_columns(df):
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


def build_student_name(df):
    nom, prenom, complet = detect_student_columns(df)
    if complet:
        return df[complet].astype(str)
    if nom and prenom:
        return df[nom].astype(str) + " " + df[prenom].astype(str)
    if nom:
        return df[nom].astype(str)
    return pd.Series([f"Eleve {i+1}" for i in range(len(df))], index=df.index)


def compute_averages(df, subject_cols):
    avgs = pd.DataFrame(index=df.index)
    for subject, cols in subject_cols.items():
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        avgs[subject] = df[cols].mean(axis=1).round(2)
    return avgs.fillna(0)


def compute_track_score(averages, track_weights):
    total_weight = sum(track_weights.get(s, 0) for s in averages.columns)
    if total_weight == 0:
        return pd.Series(0.0, index=averages.index)
    score = pd.Series(0.0, index=averages.index)
    for subject in averages.columns:
        w = track_weights.get(subject, 0)
        score += w * averages[subject]
    return ((score / total_weight) * 5).round(2)


def compute_all_scores(averages, all_track_weights):
    scores_df = pd.DataFrame(index=averages.index)
    for track, weights in all_track_weights.items():
        scores_df[track] = compute_track_score(averages, weights)
    scores_df["Score_Global"] = scores_df[TRACK_ORDER].max(axis=1)
    return scores_df


def classify_all(student_names, averages, scores_df, thresholds):
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
    result = result.sort_values("Score_Global", ascending=False).reset_index(drop=True)
    result.index = result.index + 1
    result.index.name = "Rang"
    return result


def load_css(path="style.css"):
    css_path = os.path.join(os.path.dirname(__file__), path)
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    return "<style>\n" + css + "\n</style>"


# ── HTML builders ──────────────────────────────────────────────

def html_header():
    return (
        '<div style="text-align:center;padding:.6rem 0 1.8rem">'
        '<h1 class="header-title">Systeme d\'Orientation Scolaire</h1>'
        '<p class="header-subtitle">'
        "Score par filiere, seuils et eligibilite multiple : "
        '<b class="color-sm">SM</b> &middot; '
        '<b class="color-se">SE</b> &middot; '
        '<b class="color-lt">LT</b>'
        "</p></div>"
    )


def html_welcome():
    return (
        '<div style="text-align:center;padding:3.5rem 1rem">'
        '<div class="welcome-icon">&#128194;</div>'
        '<h2 class="welcome-title">Importez un fichier Excel pour demarrer</h2>'
        "</div>"
    )


def html_seuil_scale(s_sm, s_se, s_lt):
    return (
        '<div class="seuil-container">'
        '<div style="color:rgba(255,255,255,.5);margin-bottom:.5rem">Echelle des seuils</div>'
        '<div class="seuil-track">'
        '<div class="seuil-bar"></div>'
        '<div class="seuil-marker" style="left:' + str(s_lt) + '%;background:#f06292"></div>'
        '<div class="seuil-marker" style="left:' + str(s_se) + '%;background:#22c997"></div>'
        '<div class="seuil-marker" style="left:' + str(s_sm) + '%;background:#7c6cf0"></div>'
        "</div>"
        '<div class="seuil-labels">'
        "<span>0</span>"
        '<span class="color-lt">LT &ge;' + str(s_lt) + "</span>"
        '<span class="color-se">SE &ge;' + str(s_se) + "</span>"
        '<span class="color-sm">SM &ge;' + str(s_sm) + "</span>"
        "<span>100</span>"
        "</div></div>"
    )


def html_stat_card(count, color, subtitle, pct):
    return (
        '<div class="metric-card" style="border-left:4px solid ' + color + '">'
        '<div style="color:' + color + ';font-size:2rem;font-weight:700">' + str(count) + "</div>"
        '<div style="color:rgba(255,255,255,.7);font-size:.85rem">' + subtitle + "</div>"
        '<div style="color:rgba(255,255,255,.35);font-size:.8rem">' + pct + "</div>"
        "</div>"
    )


def html_student_card(name, score, primary, pname, pcol):
    return (
        '<div class="metric-card student-card">'
        '<h3 class="student-name">' + name + "</h3>"
        '<div class="student-score" style="color:' + pcol + '">'
        + f"{score:.1f}"
        + '<span class="student-score-unit">/100</span></div>'
        '<div style="margin-top:.8rem">'
        '<span class="track-badge" style="background:' + pcol + '22;color:' + pcol
        + ";border:2px solid " + pcol + '">'
        "Recommandation : " + primary + " - " + pname
        "</span></div></div>"
    )


def html_score_row(track, name, score, threshold, color, eligible):
    cls = "eligible" if eligible else "not-eligible"
    icon = "OK" if eligible else "NON"
    pct = min(score, 100)
    return (
        '<div class="score-row ' + cls + '">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
        "<span>"
        '<span style="font-size:1rem">' + icon + "</span>"
        '<span class="score-label" style="color:' + color + '">' + track + " - " + name + "</span>"
        "</span>"
        '<span class="score-value">' + f"{score:.1f}"
        + ' <span class="score-threshold">/ seuil ' + str(threshold) + "</span></span>"
        "</div>"
        '<div class="progress-bar-bg">'
        '<div class="progress-bar-fill" style="background:' + color + ";width:" + f"{pct}" + '%"></div>'
        "</div></div>"
    )


def help_text():
    lines = [
        "**1. Score PAR FILIERE** (chaque filiere a ses propres poids) :",
        "",
        "```",
        "Score_SM = (5*Math + 3*Phys + 1*SVT + 1*Fr) / 10 * 5",
        "Score_SE = (2*Math + 3*Phys + 4*SVT + 1*Fr) / 10 * 5",
        "Score_LT = (1*Math + 1*Phys + 1*SVT + 5*Fr) / 10 * 5",
        "```",
        "",
        "Le `* 5` convertit la note /20 en pourcentage /100.",
        "",
        "**2. Eligibilite** : chaque score compare a son seuil.",
        "",
        "**3. Classement** : par le meilleur score des trois.",
    ]
    return "\n".join(lines)
        
