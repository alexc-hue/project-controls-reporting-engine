"""Risk trend metrics: exposure over time, per-risk trajectory, mitigation effectiveness.

Vendored unchanged from github.com/alexc-hue/risk-trend-tracker
(src/metrics.py).
"""

from __future__ import annotations

import pandas as pd

TREND_THRESHOLD = 2  # exposure delta at or beyond this counts as worsening/improving, not stable


def load_snapshots(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["snapshot_date", "mitigation_due_date"])
    df["exposure"] = df["probability"] * df["impact"]
    return df.sort_values(["risk_id", "snapshot_date"]).reset_index(drop=True)


def portfolio_exposure_trend(snapshots: pd.DataFrame) -> pd.DataFrame:
    """Total exposure at each snapshot date, restricted to risks tracked at
    both the first and last snapshot dates.

    Summing whatever happens to be in the register at each date conflates
    real escalation/de-escalation with risks simply entering or leaving the
    register between periods (e.g. a risk added mid-programme, or one that
    stops being reported). Restricting to the cohort of risks present at both
    ends of the window being compared keeps the reported trend a measure of
    actual movement in the risks that were tracked throughout, not an
    artifact of register churn.
    """
    dates = snapshots["snapshot_date"].sort_values().unique()
    if len(dates) == 0:
        return pd.DataFrame(columns=["snapshot_date", "total_exposure"])

    first_date, last_date = dates[0], dates[-1]
    risks_at_first = set(snapshots.loc[snapshots["snapshot_date"] == first_date, "risk_id"])
    risks_at_last = set(snapshots.loc[snapshots["snapshot_date"] == last_date, "risk_id"])
    tracked_throughout = risks_at_first & risks_at_last

    matched = snapshots[snapshots["risk_id"].isin(tracked_throughout)]
    return (
        matched.groupby("snapshot_date")["exposure"]
        .sum()
        .reset_index()
        .rename(columns={"exposure": "total_exposure"})
        .sort_values("snapshot_date")
    )


CLOSED_STATUSES = {"closed", "resolved"}


def per_risk_trajectory(snapshots: pd.DataFrame, latest_snapshot: pd.Timestamp) -> pd.DataFrame:
    """First vs. last recorded exposure per risk, classified as a trend."""
    has_status_data = "status" in snapshots.columns and snapshots["status"].notna().any()
    rows = []
    for risk_id, group in snapshots.groupby("risk_id"):
        group = group.sort_values("snapshot_date")
        first, last = group.iloc[0], group.iloc[-1]
        delta = last["exposure"] - first["exposure"]
        last_status = str(last.get("status", "")).strip().lower()
        if has_status_data:
            # Trust the actual status field: a risk that simply stopped being
            # reported (e.g. dropped from later snapshots) isn't necessarily
            # closed — only an explicit Closed/Resolved status is.
            is_closed = last_status in CLOSED_STATUSES
        else:
            # No status data at all to go on: fall back to the old
            # absence-based inference (last snapshot predates the latest one).
            is_closed = last["snapshot_date"] < latest_snapshot
        if is_closed:
            trend = "Closed/Resolved"
        elif delta >= TREND_THRESHOLD:
            trend = "Worsening"
        elif delta <= -TREND_THRESHOLD:
            trend = "Improving"
        else:
            trend = "Stable"
        rows.append({
            "risk_id": risk_id,
            "description": last["description"],
            "category": last["category"],
            "first_snapshot": first["snapshot_date"],
            "first_exposure": first["exposure"],
            "last_snapshot": last["snapshot_date"],
            "last_exposure": last["exposure"],
            "delta": delta,
            "trend": trend,
        })
    return pd.DataFrame(rows).sort_values("delta", ascending=False).reset_index(drop=True)


def mitigation_effectiveness(snapshots: pd.DataFrame) -> pd.DataFrame:
    """For risks with a mitigation due date, compare avg exposure before vs after it."""
    rows = []
    for risk_id, group in snapshots.groupby("risk_id"):
        due = group["mitigation_due_date"].iloc[0]
        if pd.isna(due):
            continue
        before = group[group["snapshot_date"] < due]["exposure"]
        after = group[group["snapshot_date"] >= due]["exposure"]
        if before.empty or after.empty:
            verdict = "Too early to assess"
            avg_before = before.mean() if not before.empty else float("nan")
            avg_after = after.mean() if not after.empty else float("nan")
        else:
            avg_before, avg_after = before.mean(), after.mean()
            verdict = "Effective" if avg_after < avg_before else "Ineffective"
        rows.append({
            "risk_id": risk_id,
            "description": group["description"].iloc[0],
            "mitigation_due_date": due,
            "avg_exposure_before": avg_before,
            "avg_exposure_after": avg_after,
            "verdict": verdict,
        })
    return pd.DataFrame(rows)


def risk_trajectory_score(exposure_trend: pd.DataFrame, effectiveness: pd.DataFrame) -> dict:
    first_total = exposure_trend["total_exposure"].iloc[0]
    last_total = exposure_trend["total_exposure"].iloc[-1]
    pct_change = (last_total - first_total) / first_total * 100 if first_total else 0.0
    trend_score = max(0.0, 50.0 - max(0.0, pct_change) * 1.5)

    assessable = effectiveness[effectiveness["verdict"] != "Too early to assess"]
    effective_count = (assessable["verdict"] == "Effective").sum()
    mitigation_score = (
        50.0 * effective_count / len(assessable) if len(assessable) else 25.0  # neutral if none assessable
    )

    total = trend_score + mitigation_score
    return {
        "first_total_exposure": first_total,
        "last_total_exposure": last_total,
        "exposure_pct_change": round(pct_change, 1),
        "trend_score": round(trend_score, 1),
        "mitigation_score": round(mitigation_score, 1),
        "total_score": round(max(0.0, min(100.0, total)), 1),
        "assessable_mitigations": len(assessable),
        "effective_mitigations": int(effective_count),
    }
