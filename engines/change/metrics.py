"""Change control metrics: cycle time, aging, and cumulative budget/schedule creep.

Vendored unchanged from github.com/alexc-hue/change-control-register
(src/metrics.py).
"""

from __future__ import annotations

import pandas as pd

STALE_PENDING_DAYS = 30  # a pending change open longer than this gets flagged


def load_change_log(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date_raised", "date_decided"])
    return df.sort_values("date_raised").reset_index(drop=True)


def add_cycle_and_aging(changes: pd.DataFrame, status_date: str) -> pd.DataFrame:
    df = changes.copy()
    status_dt = pd.Timestamp(status_date)

    decided = df["status"] != "Pending"
    df["cycle_days"] = pd.NA
    df.loc[decided, "cycle_days"] = (df.loc[decided, "date_decided"] - df.loc[decided, "date_raised"]).dt.days

    pending = df["status"] == "Pending"
    df["days_open"] = pd.NA
    df.loc[pending, "days_open"] = (status_dt - df.loc[pending, "date_raised"]).dt.days
    df["is_stale"] = pending & (df["days_open"] > STALE_PENDING_DAYS)
    return df


def cumulative_impact(changes: pd.DataFrame) -> pd.DataFrame:
    """Approved changes only, ordered by decision date, with running totals."""
    approved = changes[changes["status"] == "Approved"].sort_values("date_decided").copy()
    approved["cum_cost"] = approved["cost_impact"].cumsum()
    approved["cum_schedule_days"] = approved["schedule_impact_days"].cumsum()
    return approved


def summary_stats(changes: pd.DataFrame) -> dict:
    approved = changes[changes["status"] == "Approved"]
    rejected = changes[changes["status"] == "Rejected"]
    pending = changes[changes["status"] == "Pending"]
    decided = changes[changes["status"] != "Pending"]

    approval_rate = len(approved) / len(decided) * 100 if len(decided) else float("nan")
    cycle_values = decided["cycle_days"].dropna().astype(float)
    avg_cycle_days = cycle_values.mean() if len(cycle_values) else float("nan")

    return {
        "total_changes": len(changes),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "pending_count": len(pending),
        "stale_pending_count": int(changes["is_stale"].sum()),
        "approval_rate_pct": round(approval_rate, 1) if pd.notna(approval_rate) else None,
        "avg_cycle_days": round(avg_cycle_days, 1) if pd.notna(avg_cycle_days) else None,
        "approved_cost_impact": approved["cost_impact"].sum(),
        "approved_schedule_days": int(approved["schedule_impact_days"].sum()),
        "pending_cost_exposure": pending["cost_impact"].sum(),
        "pending_schedule_exposure_days": int(pending["schedule_impact_days"].sum()),
    }
