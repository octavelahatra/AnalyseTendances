import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
from collections import Counter
from datetime import datetime

# ------------------ Utils ------------------
def clean_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"http\S+|www\.\S+", "", s)
    s = re.sub(r"[^a-z0-9_#\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def tokenize(s: str):
    return [t for t in s.split(" ") if t and len(t) > 2]

def rolling_zscore(series, window=7):
    rmean = series.rolling(window, min_periods=3).mean()
    rstd  = series.rolling(window, min_periods=3).std(ddof=0)
    return (series - rmean) / rstd

# ------------------ Load ------------------
def load_data(path_csv: str) -> pd.DataFrame:
    df = pd.read_csv(path_csv, parse_dates=["timestamp"])
    df["date"] = df["timestamp"].dt.date
    df["clean"] = df["text"].astype(str).apply(clean_text)
    return df

# ------------------ Keyword extraction ------------------
def extract_keywords(df: pd.DataFrame, whitelist=None, top_n=20):
    all_tokens = []
    for s in df["clean"]:
        all_tokens.extend(tokenize(s))
    counts = Counter(all_tokens)
    if whitelist:
        counts = Counter({k:v for k,v in counts.items() if k in whitelist})
    # drop stop-ish words
    drop = {"the","and","for","with","this","that","after","into","look","say","week","users","people","around","reviews"}
    for w in list(counts.keys()):
        if w in drop or len(w) < 4:
            counts.pop(w, None)
    top = counts.most_common(top_n)
    return pd.DataFrame(top, columns=["keyword","count"])

# ------------------ Trends ------------------
def keyword_timeseries(df: pd.DataFrame, keyword: str):
    m = df["clean"].str.contains(fr"\b{re.escape(keyword)}\b", regex=True)
    ts = df.loc[m].groupby("date").size().rename("count").sort_index()
    return ts

def detect_trends(df: pd.DataFrame, candidate_keywords, win=7):
    rows = []
    for kw in candidate_keywords:
        ts = keyword_timeseries(df, kw)
        if ts.empty:
            continue
        z = (ts - ts.rolling(win, min_periods=3).mean()) / ts.rolling(win, min_periods=3).std(ddof=0)
        peak_z = np.nanmax(z.values) if len(z)>0 else np.nan
        recent_growth = ts.diff().rolling(3, min_periods=1).mean().iloc[-1] if len(ts)>0 else 0
        total = int(ts.sum())
        rows.append({"keyword": kw, "total_mentions": total, "peak_z": float(peak_z), "recent_growth": float(recent_growth)})
    res = pd.DataFrame(rows).sort_values(["peak_z","recent_growth","total_mentions"], ascending=False)
    return res

# ------------------ Suggest ideas ------------------
def suggest_product_idea(keyword: str) -> str:
    mapping = {
        "ecofood": "Ligne de snacks éco-responsables (bio, emballage compostable).",
        "ai_tutor": "Abonnement à un tuteur IA multilingue pour révisions scolaires.",
        "solar_cooler": "Glacière solaire portable pour marchés et pêcheurs.",
        "waterless_clean": "Nettoyant sans eau pour motos/voitures avec service à domicile.",
        "smart_agri": "Capteurs low-cost et tableau de bord pour micro-agriculteurs.",
    }
    return mapping.get(keyword, f"Prototype rapide centré sur '{keyword}' avec test panel en 2 semaines.")

# ------------------ Main pipeline ------------------
def run_pipeline(path_csv: str, whitelist=None, plot_keyword=None):
    df = load_data(path_csv)
    kws = extract_keywords(df, whitelist=whitelist, top_n=30)
    trends = detect_trends(df, kws["keyword"].tolist(), win=7)
    if plot_keyword is None and len(trends):
        plot_keyword = trends.iloc[0]["keyword"]
    if plot_keyword:
        ts = keyword_timeseries(df, plot_keyword).asfreq("D").fillna(0)
        ax = ts.plot(figsize=(9,4), title=f"Trend for '{plot_keyword}' (daily mentions)")
        ax.set_xlabel("Date")
        ax.set_ylabel("Mentions")
        plt.tight_layout()
        plt.show()
    trends["idea"] = trends["keyword"].apply(suggest_product_idea)
    return df, kws, trends

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, help="Path to CSV with posts")
    p.add_argument("--keyword", default=None, help="Keyword to plot")
    args = p.parse_args()
    _, _, trends = run_pipeline(args.data, plot_keyword=args.keyword)
    print(trends.head(10).to_string(index=False))
