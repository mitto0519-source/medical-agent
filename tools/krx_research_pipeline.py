from __future__ import annotations

import json
import math
import os
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score

YEARS = range(2020, 2027)
BASE_URL = "https://raw.githubusercontent.com/FinanceData/marcap/master/data/marcap-{year}.parquet"
RAW_DIR = Path("work/raw")
OUT_DIR = Path("output")
MONTHLY_DIR = OUT_DIR / "monthly"
RAW_DIR.mkdir(parents=True, exist_ok=True)
MONTHLY_DIR.mkdir(parents=True, exist_ok=True)

RAW_COLS = [
    "Date", "Code", "Name", "Market", "Open", "High", "Low", "Close",
    "Volume", "Amount", "Marcap", "Stocks", "ChangesRatio"
]


def rolling(grouped: pd.core.groupby.generic.SeriesGroupBy, window: int, func: str, min_periods: int | None = None) -> pd.Series:
    min_periods = min_periods or window
    obj = grouped.rolling(window, min_periods=min_periods)
    out = getattr(obj, func)()
    return out.reset_index(level=0, drop=True)


def safe_auc(y: pd.Series, p: np.ndarray) -> float:
    if y.nunique(dropna=True) < 2:
        return float("nan")
    return float(roc_auc_score(y, p))


def download_year(year: int) -> Path:
    dest = RAW_DIR / f"marcap-{year}.parquet"
    if not dest.exists() or dest.stat().st_size < 1_000_000:
        urllib.request.urlretrieve(BASE_URL.format(year=year), dest)
    return dest


def load_panel() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in YEARS:
        path = download_year(year)
        frame = pd.read_parquet(path, columns=RAW_COLS)
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame["Code"] = frame["Code"].astype(str).str.zfill(6)
        frame = frame[frame["Market"].isin(["KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"])].copy()
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(["Code", "Date"], kind="mergesort").reset_index(drop=True)
    df = df.drop_duplicates(["Date", "Code"], keep="last").reset_index(drop=True)
    return df


def engineer(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    g = df.groupby("Code", sort=False, observed=True)
    prev_close = g["Close"].shift(1)
    prev_high = g["High"].shift(1)
    prev_low = g["Low"].shift(1)

    df["ret1"] = df["Close"] / prev_close - 1.0
    for n in (2, 3, 5, 10, 20, 60):
        df[f"ret{n}"] = df["Close"] / g["Close"].shift(n) - 1.0

    df["gap"] = df["Open"] / prev_close - 1.0
    df["intraday"] = df["Close"] / df["Open"].replace(0, np.nan) - 1.0
    df["range_pct"] = (df["High"] - df["Low"]) / prev_close.replace(0, np.nan)
    candle_range = (df["High"] - df["Low"]).replace(0, np.nan)
    df["close_loc"] = (df["Close"] - df["Low"]) / candle_range
    df["upper_wick"] = (df["High"] - df[["Open", "Close"]].max(axis=1)) / candle_range
    df["lower_wick"] = (df[["Open", "Close"]].min(axis=1) - df["Low"]) / candle_range

    for n in (5, 10, 20, 60):
        ma = rolling(g["Close"], n, "mean")
        df[f"close_ma{n}"] = df["Close"] / ma - 1.0
        if n == 20:
            df["ma20_slope5"] = ma / ma.groupby(df["Code"], sort=False).shift(5) - 1.0
            df["ma20_slope10"] = ma / ma.groupby(df["Code"], sort=False).shift(10) - 1.0

    high20 = rolling(g["High"], 20, "max")
    low20 = rolling(g["Low"], 20, "min")
    df["drawdown20"] = df["Close"] / high20 - 1.0
    df["from_low20"] = df["Close"] / low20 - 1.0

    amount20 = rolling(g["Amount"], 20, "mean")
    amount5 = rolling(g["Amount"], 5, "mean")
    amount_med20 = rolling(g["Amount"], 20, "median")
    volume20 = rolling(g["Volume"], 20, "mean")
    df["amount_ratio1_20"] = df["Amount"] / amount20.replace(0, np.nan)
    df["amount_ratio5_20"] = amount5 / amount20.replace(0, np.nan)
    df["amount_ratio_med20"] = df["Amount"] / amount_med20.replace(0, np.nan)
    df["volume_ratio1_20"] = df["Volume"] / volume20.replace(0, np.nan)
    df["turnover"] = df["Volume"] / df["Stocks"].replace(0, np.nan)
    df["amount_marcap"] = df["Amount"] / df["Marcap"].replace(0, np.nan)

    true_range = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["tr_pct"] = true_range / prev_close.replace(0, np.nan)
    tr_group = df.assign(_tr=true_range).groupby("Code", sort=False, observed=True)["_tr"]
    df["atr5_pct"] = rolling(tr_group, 5, "mean") / df["Close"].replace(0, np.nan)
    df["atr20_pct"] = rolling(tr_group, 20, "mean") / df["Close"].replace(0, np.nan)

    ret_group = df.groupby("Code", sort=False, observed=True)["ret1"]
    df["ret_vol5"] = rolling(ret_group, 5, "std")
    df["ret_vol20"] = rolling(ret_group, 20, "std")

    past_limit = (df["ret1"] >= 0.29).groupby(df["Code"], sort=False).shift(1)
    past_p10 = (df["ret1"] >= 0.10).groupby(df["Code"], sort=False).shift(1)
    df["limit_count20"] = past_limit.groupby(df["Code"], sort=False).rolling(20, min_periods=5).sum().reset_index(level=0, drop=True)
    df["p10_count20"] = past_p10.groupby(df["Code"], sort=False).rolling(20, min_periods=5).sum().reset_index(level=0, drop=True)
    df["max_ret20"] = ret_group.shift(1).groupby(df["Code"], sort=False).rolling(20, min_periods=5).max().reset_index(level=0, drop=True)
    df["max_amount_ratio20"] = df["amount_ratio_med20"].groupby(df["Code"], sort=False).shift(1).groupby(df["Code"], sort=False).rolling(20, min_periods=5).max().reset_index(level=0, drop=True)

    # Cross-sectional energy/state variables known at each close.
    for col in ("atr20_pct", "turnover", "amount_marcap", "range_pct"):
        df[f"{col}_pctile"] = df.groupby("Date", observed=True)[col].rank(pct=True)
    df["energy_count"] = sum((df[f"{c}_pctile"] >= 0.75).astype(int) for c in ("atr20_pct", "turnover", "amount_marcap", "range_pct"))
    df["size_pctile"] = df.groupby("Date", observed=True)["Marcap"].rank(pct=True)

    # Daily market context.
    valid_ret = df["ret1"].replace([np.inf, -np.inf], np.nan)
    tmp = df.assign(_ret=valid_ret)
    daily = tmp.groupby("Date", observed=True).agg(
        breadth_up=("_ret", lambda s: float((s > 0).mean())),
        breadth_p5=("_ret", lambda s: float((s >= 0.05).mean())),
        breadth_m5=("_ret", lambda s: float((s <= -0.05).mean())),
        breadth_p10=("_ret", lambda s: float((s >= 0.10).mean())),
        limit_density=("_ret", lambda s: float((s >= 0.29).mean())),
        market_median_ret=("_ret", "median"),
        market_dispersion=("_ret", "std"),
        total_amount=("Amount", "sum"),
    ).reset_index()
    daily["total_amount_ratio20"] = daily["total_amount"] / daily["total_amount"].rolling(20, min_periods=5).mean()
    daily["limit_density20"] = daily["limit_density"].rolling(20, min_periods=5).mean()

    small = tmp[tmp["size_pctile"] <= 0.30].groupby("Date", observed=True)["_ret"].mean().rename("small_ret")
    large = tmp[tmp["size_pctile"] >= 0.70].groupby("Date", observed=True)["_ret"].mean().rename("large_ret")
    daily = daily.merge(small, on="Date", how="left").merge(large, on="Date", how="left")
    daily["small_large_rotation"] = daily["small_ret"] - daily["large_ret"]
    df = df.merge(daily, on="Date", how="left")

    market_daily = tmp.groupby(["Date", "Market"], observed=True).agg(
        venue_breadth=("_ret", lambda s: float((s > 0).mean())),
        venue_amount=("Amount", "sum"),
        venue_median_ret=("_ret", "median"),
    ).reset_index()
    market_daily["venue_amount_ratio20"] = market_daily.groupby("Market", observed=True)["venue_amount"].transform(lambda s: s / s.rolling(20, min_periods=5).mean())
    df = df.merge(market_daily, on=["Date", "Market"], how="left")

    # Labels from future path; never used as features.
    next_close = g["Close"].shift(-1)
    next_high = g["High"].shift(-1)
    next_low = g["Low"].shift(-1)
    n2_high = pd.concat([next_high, g["High"].shift(-2)], axis=1).max(axis=1)
    n2_close = g["Close"].shift(-2)
    df["y_up1"] = (next_close > df["Close"]).astype(float)
    df["y_bad5"] = (next_low / df["Close"] - 1.0 <= -0.05).astype(float)
    df["y_p10"] = (next_high / df["Close"] - 1.0 >= 0.10).astype(float)
    df["y_p20"] = (next_high / df["Close"] - 1.0 >= 0.20).astype(float)
    df["y_up2"] = (n2_close > df["Close"]).astype(float)
    df["y_n2_p10"] = (n2_high / df["Close"] - 1.0 >= 0.10).astype(float)
    df["y_n2_p20"] = (n2_high / df["Close"] - 1.0 >= 0.20).astype(float)
    df["next_close_ret"] = next_close / df["Close"] - 1.0
    df["next_mfe"] = next_high / df["Close"] - 1.0
    df["next_mae"] = next_low / df["Close"] - 1.0

    feature_cols = [
        "ret1", "ret2", "ret3", "ret5", "ret10", "ret20", "ret60",
        "gap", "intraday", "range_pct", "close_loc", "upper_wick", "lower_wick",
        "close_ma5", "close_ma10", "close_ma20", "close_ma60", "ma20_slope5", "ma20_slope10",
        "drawdown20", "from_low20", "amount_ratio1_20", "amount_ratio5_20", "amount_ratio_med20",
        "volume_ratio1_20", "turnover", "amount_marcap", "tr_pct", "atr5_pct", "atr20_pct",
        "ret_vol5", "ret_vol20", "limit_count20", "p10_count20", "max_ret20", "max_amount_ratio20",
        "energy_count", "size_pctile", "breadth_up", "breadth_p5", "breadth_m5", "breadth_p10",
        "limit_density", "market_median_ret", "market_dispersion", "total_amount_ratio20", "limit_density20",
        "small_large_rotation", "venue_breadth", "venue_amount_ratio20", "venue_median_ret",
    ]
    return df, feature_cols


def route_name(row: pd.Series) -> str:
    if row.get("ret1", 0) >= 0.25:
        return "SERIAL_ACTIVE_OR_ALREADY_EXTENDED"
    if row.get("limit_count20", 0) >= 1 and row.get("max_amount_ratio20", 0) >= 3:
        return "REACTIVATION_MARKUP_MEMORY"
    if row.get("ret20", 0) <= -0.10 and row.get("drawdown20", 0) <= -0.15:
        if row.get("close_loc", 0) >= 0.70 and row.get("ret1", 0) > 0:
            return "WASHOUT_REARM"
        return "QUIET_LOW_BASE"
    if row.get("ma20_slope5", 0) > 0 and abs(row.get("close_ma20", 0)) <= 0.05:
        return "TREND_PULLBACK_ACCEPTANCE"
    if row.get("energy_count", 0) >= 3:
        return "HIGH_ENERGY_EXPANSION"
    return "NORMAL_TRANSITION"


def fit_model(x: pd.DataFrame, y: pd.Series, rare: bool = False) -> LGBMClassifier:
    model = LGBMClassifier(
        objective="binary",
        n_estimators=180,
        learning_rate=0.045,
        num_leaves=31,
        max_depth=-1,
        min_child_samples=80,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_alpha=0.25,
        reg_lambda=1.0,
        class_weight="balanced" if rare else None,
        random_state=20260821,
        n_jobs=-1,
        verbosity=-1,
    )
    model.fit(x, y)
    return model


def main() -> None:
    df = load_panel()
    df, features = engineer(df)

    # Persist month-by-month raw panels so later reverse-daily validation can resume without redownloading.
    export_cols = RAW_COLS + ["ret1"]
    for period, part in df.groupby(df["Date"].dt.to_period("M"), observed=True):
        part[export_cols].to_parquet(MONTHLY_DIR / f"krx_{period}.parquet", index=False, compression="zstd")

    latest = df["Date"].max()
    label_known = df["Date"] < latest
    usable = (
        label_known
        & df[features].notna().sum(axis=1).ge(int(len(features) * 0.80))
        & df["Close"].gt(100)
        & df["Amount"].gt(0)
        & df["ret1"].abs().le(0.35)
    )
    train_long = usable & (df["Date"] <= pd.Timestamp("2025-12-31"))
    validate = usable & (df["Date"] >= pd.Timestamp("2026-04-01"))
    train_current = usable

    x_all = df[features].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype("float32")
    targets = {
        "up": ("y_up1", False),
        "bad5": ("y_bad5", True),
        "p10": ("y_p10", True),
        "p20": ("y_p20", True),
        "up2": ("y_up2", False),
        "n2p10": ("y_n2_p10", True),
        "n2p20": ("y_n2_p20", True),
    }

    metrics: list[dict[str, float | str | int]] = []
    long_models: dict[str, LGBMClassifier] = {}
    current_models: dict[str, LGBMClassifier] = {}
    for key, (target, rare) in targets.items():
        long_model = fit_model(x_all.loc[train_long], df.loc[train_long, target].astype(int), rare=rare)
        long_models[key] = long_model
        pv = long_model.predict_proba(x_all.loc[validate])[:, 1]
        yv = df.loc[validate, target].astype(int)
        metrics.append({
            "model": f"long_{key}",
            "train_start": str(df.loc[train_long, "Date"].min().date()),
            "train_end": str(df.loc[train_long, "Date"].max().date()),
            "validation_start": str(df.loc[validate, "Date"].min().date()),
            "validation_end": str(df.loc[validate, "Date"].max().date()),
            "n_train": int(train_long.sum()),
            "n_validation": int(validate.sum()),
            "base_rate": float(yv.mean()),
            "auc": safe_auc(yv, pv),
            "brier": float(brier_score_loss(yv, pv)),
        })
        current_models[key] = fit_model(x_all.loc[train_current], df.loc[train_current, target].astype(int), rare=rare)

    latest_mask = df["Date"].eq(latest)
    cand = df.loc[latest_mask].copy()
    x_latest = x_all.loc[latest_mask]
    for key in targets:
        cand[f"p_{key}_long"] = long_models[key].predict_proba(x_latest)[:, 1]
        cand[f"p_{key}"] = current_models[key].predict_proba(x_latest)[:, 1]

    # Shrink current estimate toward multi-year estimate, preserving recent style without letting it dominate.
    for key in targets:
        cand[f"p_{key}_blend"] = 0.65 * cand[f"p_{key}_long"] + 0.35 * cand[f"p_{key}"]

    cand["route"] = cand.apply(route_name, axis=1)
    cand["direction_edge"] = cand["p_up_blend"] - cand["p_bad5_blend"]
    cand["tail_value"] = 0.70 * cand["p_p10_blend"] + 0.30 * cand["p_p20_blend"]
    cand["n2_tail_value"] = 0.70 * cand["p_n2p10_blend"] + 0.30 * cand["p_n2p20_blend"]
    cand["pick_score"] = cand["direction_edge"] + 0.15 * cand["tail_value"] + 0.05 * cand["n2_tail_value"]

    name = cand["Name"].fillna("").astype(str)
    cand["execution_eligible"] = (
        ~name.str.contains("스팩|SPAC|ETF|ETN", case=False, regex=True)
        & cand["Close"].gt(300)
        & cand["Volume"].gt(0)
        & cand["ret1"].between(-0.15, 0.12)
        & ~((cand["High"].eq(cand["Low"])) & cand["ret1"].ge(0.20))
    )
    cand["direction_gate"] = (cand["p_up_blend"] >= 0.58) & (cand["p_bad5_blend"] <= 0.10)
    ranked = cand[cand["execution_eligible"]].sort_values(
        ["direction_gate", "pick_score", "direction_edge"], ascending=[False, False, False]
    )

    output_cols = [
        "Date", "Code", "Name", "Market", "Close", "Open", "High", "Low", "Volume", "Amount", "Marcap",
        "ret1", "ret5", "ret20", "drawdown20", "close_ma20", "ma20_slope5", "close_loc",
        "amount_ratio1_20", "amount_ratio5_20", "turnover", "amount_marcap", "atr20_pct", "energy_count",
        "limit_count20", "p10_count20", "breadth_up", "total_amount_ratio20", "small_large_rotation",
        "route", "p_up_blend", "p_bad5_blend", "p_p10_blend", "p_p20_blend", "p_up2_blend",
        "p_n2p10_blend", "p_n2p20_blend", "direction_edge", "tail_value", "pick_score",
        "direction_gate", "execution_eligible",
    ]
    ranked[output_cols].head(100).to_csv(OUT_DIR / "latest_candidates.csv", index=False, encoding="utf-8-sig")
    cand[output_cols].to_parquet(OUT_DIR / "latest_full_snapshot.parquet", index=False, compression="zstd")
    pd.DataFrame(metrics).to_csv(OUT_DIR / "model_metrics.csv", index=False)

    # Genuine 2026 daily OOS top-one using only the 2020-2025 model.
    valid_df = df.loc[validate].copy()
    x_valid = x_all.loc[validate]
    for key in targets:
        valid_df[f"p_{key}"] = long_models[key].predict_proba(x_valid)[:, 1]
    valid_df["direction_edge"] = valid_df["p_up"] - valid_df["p_bad5"]
    valid_df["score"] = valid_df["direction_edge"] + 0.15 * (0.70 * valid_df["p_p10"] + 0.30 * valid_df["p_p20"])
    vn = valid_df["Name"].fillna("").astype(str)
    valid_df = valid_df[
        ~vn.str.contains("스팩|SPAC|ETF|ETN", case=False, regex=True)
        & valid_df["ret1"].between(-0.15, 0.12)
        & valid_df["Close"].gt(300)
        & valid_df["Volume"].gt(0)
    ]
    daily_top = valid_df.sort_values(["Date", "score"], ascending=[True, False]).groupby("Date", as_index=False).head(1)
    daily_top[[
        "Date", "Code", "Name", "Market", "Close", "score", "p_up", "p_bad5", "p_p10", "p_p20",
        "next_close_ret", "next_mfe", "next_mae", "y_up1", "y_p10", "y_p20", "y_bad5"
    ]].to_csv(OUT_DIR / "daily_top1_oos_2026.csv", index=False, encoding="utf-8-sig")

    pick = ranked.iloc[0] if not ranked.empty else None
    summary = {
        "latest_date": str(latest.date()),
        "panel_start": str(df["Date"].min().date()),
        "panel_end": str(df["Date"].max().date()),
        "rows": int(len(df)),
        "codes": int(df["Code"].nunique()),
        "candidate_count": int(len(ranked)),
        "direction_gate_count": int(ranked["direction_gate"].sum()) if not ranked.empty else 0,
        "pick1": None if pick is None else {
            "code": str(pick["Code"]),
            "name": str(pick["Name"]),
            "market": str(pick["Market"]),
            "close": float(pick["Close"]),
            "route": str(pick["route"]),
            "p_up": float(pick["p_up_blend"]),
            "p_bad5": float(pick["p_bad5_blend"]),
            "p_p10": float(pick["p_p10_blend"]),
            "p_p20": float(pick["p_p20_blend"]),
            "p_up2": float(pick["p_up2_blend"]),
            "p_n2p10": float(pick["p_n2p10_blend"]),
            "p_n2p20": float(pick["p_n2p20_blend"]),
            "score": float(pick["pick_score"]),
            "direction_gate": bool(pick["direction_gate"]),
        },
        "daily_oos": {
            "days": int(len(daily_top)),
            "up_rate": float(daily_top["y_up1"].mean()) if len(daily_top) else None,
            "mean_close_ret": float(daily_top["next_close_ret"].mean()) if len(daily_top) else None,
            "median_close_ret": float(daily_top["next_close_ret"].median()) if len(daily_top) else None,
            "p10_rate": float(daily_top["y_p10"].mean()) if len(daily_top) else None,
            "p20_rate": float(daily_top["y_p20"].mean()) if len(daily_top) else None,
            "bad5_rate": float(daily_top["y_bad5"].mean()) if len(daily_top) else None,
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
