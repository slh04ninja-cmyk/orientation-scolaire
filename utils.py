from io import StringIO  # ✅ CORRECTION: import standard au lieu de pd.io.common.StringIO

import pandas as pd
import numpy as np


SUBJECT_PATTERNS = {
    "Mathematiques": ["mathematiques", "maths", "math", "mathe"],
    "Physique": ["physique", "phys", "chimie"],
    "SVT": ["svt", "biologie", "sciences de la vie"],
    "Francais": ["francais", "lf", "langue francaise"],
}

TRACK_ORDER = ["SM", "SE", "LT"]
TRACK_NAMES = {
    "SM": "Sciences Mathematiques",
    "SE": "Sciences Experimentales",
    "LT": "Lettres et Traduction",
}
TRACK_COLORS = {"SM": "#7c6cf0", "SE": "#22c997", "LT": "#f06292"}

DEFAULT_TRACK_WEIGHTS = {
    "SM": {"Mathematiques": 5.0, "Physique": 3.0, "SVT": 1.0, "Francais": 1.0},
    "SE": {"Mathematiques": 2.0, "Physique": 3.0, "SVT": 4.0, "Francais": 1.0},
    "LT": {"Mathematiques": 1.0, "Physique": 1.0, "SVT": 1.0, "Francais": 5.0},
}

DEFAULT_THRESHOLDS = {"SM": 70, "SE": 50, "LT": 30}


def get_css():
    return """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
.stApp { background: #0e0e1a; color: #e0e0e0; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b0b18 0%, #151530 100%);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.block-container { padding-top: 2rem; max-width: 1200px; }

.metric-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 18px;
    padding: 1.6rem 1.4rem;
    backdrop-filter: blur(12px);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.metric-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 14px 44px rgba(0, 0, 0, 0.35);
}

.track-badge {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 30px;
    font-weight: 600;
    font-size: 0.8rem;
    margin: 2px;
}

[data-testid="stFileUploadDropzone"] {
    border: 2px dashed rgba(255, 255, 255, 0.12) !important;
    border-radius: 16px !important;
}
[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; }
hr { border-color: rgba(255, 255, 255, 0.06) !important; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.12); border-radius: 6px; }

.header-title {
    font-size: 2.4rem;
    margin-bottom: 0.3rem;
    background: linear-gradient(135deg, #7c6cf0, #22c997, #f06292);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.header-subtitle { color: rgba(255, 255, 255, 0.55); font-size: 1.05rem; max-width: 700px; margin: auto; }

.welcome-icon { font-size: 4rem; margin-bottom: 0.8rem; }
.welcome-title { color: rgba(255, 255, 255, 0.75); font-weight: 400; }

.score-row { margin: 8px 0; padding: 10px 14px; border-radius: 12px; }
.score-row.eligible { background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.1); }
.score-row.not-eligible { background: rgba(255, 255, 255, 0.015); border: 1px solid rgba(255, 255, 255, 0.04); }
.score-label { font-weight: 600; margin-left: 6px; }
.score-value { color: rgba(255, 255, 255, 0.7); font-weight: 600; font-family: 'JetBrains Mono', monospace; }
.score-threshold { font-size: 0.7rem; color: rgba(255, 255, 255, 0.35); }

.progress-bar-bg { background: rgba(255, 255, 255, 0.08); border-radius: 8px; height: 8px; }
.progress-bar-fill { height: 100%; border-radius: 8px; transition: width 0.5s ease; }

.seuil-container { margin-top: 0.8rem; padding: 0.8rem 1rem; background: rgba(255, 255, 255, 0.03); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.06); font-size: 0.85rem; }
.seuil-track { position: relative; height: 30px; margin: 8px 0; }
.seuil-bar { position: absolute; top: 12px; left: 0; right: 0; height: 6px; background: linear-gradient(90deg, #f06292, #22c997, #7c6cf0); border-radius: 6px; }
.seuil-marker { position: absolute; top: 6px; width: 18px; height: 18px; border-radius: 50%; border: 2px solid #0e0e1a; transform: translateX(-50%); }
.seuil-labels { display: flex; justify-content: space-between; color: rgba(255, 255, 255, 0.4); font-size: 0.75rem; }

.student-card { text-align: center; padding: 2rem 1.4rem; }
.student-name { color: #fff; margin-bottom: 0.6rem; }
.student-score { font-size: 2.4rem; font-weight: 800; }
.student-score-unit { font-size: 1rem; font-weight: 400; color: rgba(255, 255, 255, 0.4); }

.color-sm { color: #7c6cf0; }
.color-se { color: #22c997; }
.color-lt { color: #f06292; }
"""


def read_excel_safe(uploaded_file):
    errors = []
    # ✅ CORRECTION: openpyxl en premier (toujours disponible), calamine en dernier
    for engine in ("openpyxl", "xlrd", "calamine"):
        try:
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file, engine=engine)
        except Exception as e:
            errors.append(engine + " : " + str(e))
    for sep in ("\t", ";", ","):
        try:
            uploaded_file.seek(0)
            raw = uploaded_file.read().decode("utf-8", errors="replace")
            # ✅ CORRECTION: StringIO importé en haut au lieu de pd.io.common.StringIO
            df = pd.read_csv(StringIO(raw), sep=sep)
            if len(df.columns) > 1:
                return df
        except Exception as e:
            errors.append("csv : " + str(e))
    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read().decode("utf-8", errors="replace")
        # ✅ CORRECTION: StringIO importé en haut au lieu de pd.io.common.StringIO
        df = pd.read_csv(StringIO(raw), sep=None, engine="python")
        if len(df.columns) > 1:
            return df
    except Exception as e:
        errors.append("csv_auto : " + str(e))
    raise RuntimeError("Lecture impossible.\n" + "\n".join(errors))


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
    nom = None
    prenom = None
    complet = None
    for col in df.columns:
        low = col.lower().strip()
        if any(k in low for k in ["nom et prenom", "nom_complet", "nom complet", "eleve"]):
            complet = col
        elif any(k in low for k in ["prenom", "first name"]):
            prenom = col
        elif any(k in low for k in ["nom", "name", "last name", "famille"]):
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
    return pd.Series(["Eleve " + str(i + 1) for i in range(len(df))], index=df.index)


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
            row["Score " + track] = scores_df[track].iloc[idx]
        row["Score_Global"] = scores_df["Score_Global"].iloc[idx]
        eligible = []
        for track in TRACK_ORDER:
            if row["Score " + track] >= thresholds.get(track, 0):
                eligible.append(track)
        row["Filiere principale"] = eligible[0] if eligible else "---"
        row["Eligibilite"] = " | ".join(eligible) if eligible else "Aucune"
        row["Nb filieres"] = len(eligible)
        for subj in averages.columns:
            row["Moy. " + subj] = averages.iloc[idx].get(subj, 0)
        rows.append(row)
    result = pd.DataFrame(rows)
    result = result.sort_values("Score_Global", ascending=False).reset_index(drop=True)
    result.index = result.index + 1
    result.index.name = "Rang"
    return result


def html_header():
    s = '<div style="text-align:center;padding:.6rem 0 1.8rem">'
    s += '<h1 class="header-title">Systeme d\'Orientation Scolaire</h1>'
    s += '<p class="header-subtitle">'
    s += 'Score par filiere, seuils et eligibilite multiple : '
    s += '<b class="color-sm">SM</b> &middot; '
    s += '<b class="color-se">SE</b> &middot; '
    s += '<b class="color-lt">LT</b>'
    s += '</p></div>'
    return s


def html_welcome():
    s = '<div style="text-align:center;padding:3.5rem 1rem">'
    s += '<div class="welcome-icon">&#128194;</div>'
    s += '<h2 class="welcome-title">Importez un fichier Excel pour demarrer</h2>'
    s += '</div>'
    return s


def html_seuil_scale(s_sm, s_se, s_lt):
    s = '<div class="seuil-container">'
    s += '<div style="color:rgba(255,255,255,.5);margin-bottom:.5rem">Echelle des seuils</div>'
    s += '<div class="seuil-track">'
    s += '<div class="seuil-bar"></div>'
    s += '<div class="seuil-marker" style="left:' + str(s_lt) + '%;background:#f06292"></div>'
    s += '<div class="seuil-marker" style="left:' + str(s_se) + '%;background:#22c997"></div>'
    s += '<div class="seuil-marker" style="left:' + str(s_sm) + '%;background:#7c6cf0"></div>'
    s += '</div>'
    s += '<div class="seuil-labels">'
    s += '<span>0</span>'
    s += '<span class="color-lt">LT &ge;' + str(s_lt) + '</span>'
    s += '<span class="color-se">SE &ge;' + str(s_se) + '</span>'
    s += '<span class="color-sm">SM &ge;' + str(s_sm) + '</span>'
    s += '<span>100</span>'
    s += '</div></div>'
    return s


def html_stat_card(count, color, subtitle, pct):
    s = '<div class="metric-card" style="border-left:4px solid ' + color + '">'
    s += '<div style="color:' + color + ';font-size:2rem;font-weight:700">' + str(count) + '</div>'
    s += '<div style="color:rgba(255,255,255,.7);font-size:.85rem">' + subtitle + '</div>'
    s += '<div style="color:rgba(255,255,255,.35);font-size:.8rem">' + pct + '</div>'
    s += '</div>'
    return s


def html_student_card(name, score, primary, pname, pcol):
    s = '<div class="metric-card student-card">'
    s += '<h3 class="student-name">' + name + '</h3>'
    s += '<div class="student-score" style="color:' + pcol + '">'
    s += f"{score:.1f}"
    s += '<span class="student-score-unit">/100</span></div>'
    s += '<div style="margin-top:.8rem">'
    s += '<span class="track-badge" style="background:' + pcol + '22;color:' + pcol
    s += ';border:2px solid ' + pcol + '">'
    s += 'Recommandation : ' + primary + ' - ' + pname
    s += '</span></div></div>'
    return s


def html_score_row(track, name, score, threshold, color, eligible):
    cls = "eligible" if eligible else "not-eligible"
    icon = "OK" if eligible else "NON"
    pct = min(score, 100)
    s = '<div class="score-row ' + cls + '">'
    s += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
    s += '<span>'
    s += '<span style="font-size:1rem">' + icon + '</span>'
    s += '<span class="score-label" style="color:' + color + '">' + track + ' - ' + name + '</span>'
    s += '</span>'
    s += '<span class="score-value">' + f"{score:.1f}"
    s += ' <span class="score-threshold">/ seuil ' + str(threshold) + '</span></span>'
    s += '</div>'
    s += '<div class="progress-bar-bg">'
    s += '<div class="progress-bar-fill" style="background:' + color + ';width:' + f"{pct}" + '%"></div>'
    s += '</div></div>'
    return s


def help_text():
    lines = []
    lines.append("**1. Score PAR FILIERE** (chaque filiere a ses propres poids) :")
    lines.append("")
    lines.append("```")
    lines.append("Score_SM = (5*Math + 3*Phys + 1*SVT + 1*Fr) / 10 * 5")
    lines.append("Score_SE = (2*Math + 3*Phys + 4*SVT + 1*Fr) / 10 * 5")
    lines.append("Score_LT = (1*Math + 1*Phys + 1*SVT + 5*Fr) / 10 * 5")
    lines.append("```")
    lines.append("")
    lines.append("Le `* 5` convertit la note /20 en pourcentage /100.")
    lines.append("")
    lines.append("**2. Eligibilite** : chaque score compare a son seuil.")
    lines.append("")
    lines.append("**3. Classement** : par le meilleur score des trois.")
    return "\n".join(lines)
