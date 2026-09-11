"""Change control metrics: cycle time, aging, and cumulative budget/schedule creep.

Vendored unchanged from github.com/alexc-hue/change-control-register
(src/metrics.py).

Deliberately does not roll up into a single opinionated "score" the way the
schedule health tool does: approved change cost isn't inherently bad (a lot
of it is legitimate client-driven scope growth), so collapsing cost/schedule
impact into a good/bad number would be misleading. This tool reports clear
descriptive metrics and flags instead.
"""

from __future__ import annotations

import pandas as pd

STALE_PENDING_DAYS = 30  # a pending change open longer than this gets flagged


def _is_decided(df: pd.DataFrame) -> pd.Series:
    """A change is "decided" when it actually has a decision date, not merely
    whenever its status isn't "Pending" — that would also catch any other
    non-pending-but-undecided status (e.g. "Cancelled", "On Hold")."""
    return df["date_decided"].notna()


def load_change_log(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date_raised", "date_decided"])
    return df.sort_values("date_raised").reset_index(drop=True)


def add_cycle_and_aging(changes: pd.DataFrame, status_date: str) -> pd.DataFrame:
    df = changes.copy()
    status_dt = pd.Timestamp(status_date)

    # See _is_decided() above: a change is "decided" when it has an actual
    # decision date, not merely whenever its status isn't "Pending" (which
    # would also catch e.g. "Cancelled"/"On Hold" and leave cycle_days as NaN
    # for those rows).
    decided = _is_decided(df)
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
    # Same _is_decided() definition used in add_cycle_and_aging.
    decided = changes[_is_decided(changes)]

    # approval_rate_pct's numerator has to be a subset of its denominator (both
    # "decided"), or an "Approved" row with no decision date would count in
    # the numerator without ever counting in "decided", pushing the rate past
    # 100%. Surfaced separately too, since an approved change missing its
    # decision date is itself a data-quality issue worth flagging, not just
    # something to quietly work around.
    approved_decided = approved[_is_decided(approved)]
    approved_missing_decision_date = len(approved) - len(approved_decided)

    approval_rate = len(approved_decided) / len(decided) * 100 if len(decided) else float("nan")
    cycle_values = decided["cycle_days"].dropna().astype(float)
    avg_cycle_days = cycle_values.mean() if len(cycle_values) else float("nan")

    return {
        "total_changes": len(changes),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "pending_count": len(pending),
        "stale_pending_count": int(changes["is_stale"].sum()),
        "approved_missing_decision_date": approved_missing_decision_date,
        "approval_rate_pct": round(approval_rate, 1) if pd.notna(approval_rate) else None,
        "avg_cycle_days": round(avg_cycle_days, 1) if pd.notna(avg_cycle_days) else None,
        "approved_cost_impact": approved["cost_impact"].sum(),
        "approved_schedule_days": int(approved["schedule_impact_days"].sum()),
        "pending_cost_exposure": pending["cost_impact"].sum(),
        "pending_schedule_exposure_days": int(pending["schedule_impact_days"].sum()),
    }
