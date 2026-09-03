"""
Project Controls Reporting Engine
------------------------------------
Composes the four tools in the project-controls toolkit (EVM dashboard,
schedule health, change control, risk trend) against ONE consistent
fictional programme, and produces a single integrated status report.

This adds no new analytical logic. It imports each tool's existing,
already-published metrics module unchanged (see engines/) and runs them
against one shared story, then reports what the four disciplines'
independent computations say about the same programme, side by side.

Run:
    pip install -r requirements.txt
    python reporting_engine.py
"""

import os

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from engines.dashboard import metrics as dash
from engines.schedule import metrics as sched
from engines.change import metrics as chg
from engines.risk import metrics as risk

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

BAC = 2_400_000
PROJECT_START = "2026-01-05"
PLANNED_FINISH = "2026-08-03"
STATUS_DATE = "2026-08-01"

# Standardized chart color system (chart chrome, status scale, categorical series)
CHART_BG = "#fcfcfb"
INK = "#10182b"
GRID = "#e1e0d9"
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"
SERIES_3 = "#1baf7a"
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_CRITICAL = "#d03b3b"


def _apply_chrome(fig, axes) -> None:
    """Apply the standardized chart chrome (background, ink, gridlines) to a figure."""
    fig.patch.set_facecolor(CHART_BG)
    if hasattr(axes, "flatten"):
        axes = axes.flatten().tolist()
    elif not isinstance(axes, (list, tuple)):
        axes = [axes]
    for ax in axes:
        ax.set_facecolor(CHART_BG)
        ax.title.set_color(INK)
        ax.xaxis.label.set_color(INK)
        ax.yaxis.label.set_color(INK)
        ax.tick_params(colors=INK)
        for spine in ax.spines.values():
            spine.set_color(INK)


def money(x: float) -> str:
    return f"${x:,.0f}"


def run_dashboard_engine():
    ts = dash.load_timeseries(os.path.join(DATA_DIR, "cost_schedule_timeseries.csv"))
    milestones = dash.load_milestones(os.path.join(DATA_DIR, "milestones.csv"))
    risks = dash.load_risk_register(os.path.join(DATA_DIR, "risk_register.csv"), STATUS_DATE)
    changes = dash.load_change_register(os.path.join(DATA_DIR, "change_register.csv"))
    summary = dash.project_summary(ts, BAC)
    forecast_finish = dash.forecast_completion_date(milestones, summary["spi"], PROJECT_START, PLANNED_FINISH)
    change_summary = dash.change_impact_summary(changes, BAC)
    return {
        "ts": ts, "milestones": milestones, "risks": risks, "changes": changes,
        "summary": summary, "forecast_finish": forecast_finish, "change_summary": change_summary,
    }


def run_schedule_engine():
    activities = sched.load_activities(os.path.join(DATA_DIR, "activities.csv"))
    baseline, current = sched.run_baseline_and_current(activities, PROJECT_START)
    comparison = sched.compare_schedules(activities, baseline, current)
    score = sched.schedule_health_score(comparison, baseline.project_finish, current.project_finish)
    return {"baseline": baseline, "current": current, "comparison": comparison, "score": score}


def run_change_engine():
    raw = chg.load_change_log(os.path.join(DATA_DIR, "change_log.csv"))
    changes = chg.add_cycle_and_aging(raw, STATUS_DATE)
    cum = chg.cumulative_impact(changes)
    stats = chg.summary_stats(changes)
    return {"changes": changes, "cum": cum, "stats": stats}


def run_risk_engine():
    snapshots = risk.load_snapshots(os.path.join(DATA_DIR, "risk_snapshots.csv"))
    exposure_trend = risk.portfolio_exposure_trend(snapshots)
    latest = snapshots["snapshot_date"].max()
    trajectory = risk.per_risk_trajectory(snapshots, latest)
    effectiveness = risk.mitigation_effectiveness(snapshots)
    score = risk.risk_trajectory_score(exposure_trend, effectiveness)
    return {"snapshots": snapshots, "exposure_trend": exposure_trend,
            "trajectory": trajectory, "effectiveness": effectiveness, "score": score}


def print_report(d: dict, s: dict, c: dict, r: dict) -> None:
    ds, ss, cs, rs = d["summary"], s["score"], c["stats"], r["score"]

    print("=" * 68)
    print("INTEGRATED PROGRAMME STATUS REPORT")
    print("Ridgeline LNG Compressor Station Retrofit — as of", STATUS_DATE)
    print("=" * 68)
    print()
    print(f"COST / EVM (dashboard engine)")
    print(f"  SPI {ds['spi']:.2f}  CPI {ds['cpi']:.2f}  EAC {money(ds['eac'])}  "
          f"VAC {money(ds['vac'])}")
    print()
    print(f"SCHEDULE (schedule health engine)")
    print(f"  Schedule Health Score: {ss['total_score']}/100  "
          f"Slip: {ss['slip_days']:+d}d  "
          f"Critical/near-critical: {ss['pct_activities_critical_or_near']}%")
    print()
    print(f"CHANGE CONTROL (change engine)")
    print(f"  Approved: {money(cs['approved_cost_impact'])}  "
          f"({cs['approved_schedule_days']:+d}d)   "
          f"Pending: {money(cs['pending_cost_exposure'])}   "
          f"Stale pending: {cs['stale_pending_count']}")
    print()
    print(f"RISK (risk trend engine)")
    print(f"  Risk Trajectory Score: {rs['total_score']}/100  "
          f"Exposure change: {rs['exposure_pct_change']:+.1f}%   "
          f"Effective mitigations: {rs['effective_mitigations']}/{rs['assessable_mitigations']}")

    print()
    print("-" * 68)
    print("INTEGRATED OBSERVATIONS")
    print("-" * 68)
    print()
    print("One root cause is visible independently across all four disciplines: the")
    print("compressor rotor procurement delay (activity P1, +30 days against baseline).")
    print()
    print(f"  - Schedule: that single activity is the reason for the programme's "
          f"entire {ss['slip_days']}-day slip, and {ss['pct_activities_critical_or_near']}% "
          f"of activities are now critical or near-critical as a direct result.")
    print()
    print(f"  - Cost: CPI has fallen to {ds['cpi']:.2f} over the same window the delay "
          f"unfolded, and {money(cs['approved_cost_impact'])} of the approved change "
          f"impact ({cs['approved_schedule_days']:+d} net days) is the cost of "
          f"responding to it, chiefly the expedited air-freight change that clawed "
          f"back schedule at a cost.")
    print()
    print("  - Risk: the procurement-capacity risk (R01) was already flagged and "
          "escalating months before the delay materialized, and its mitigation "
          "closed after the risk had already converted into an actual schedule "
          "hit, a live example of exactly what a risk register tracked as a trend "
          "is supposed to catch, and a single snapshot would have missed.")
    print()
    print("None of this is a new predictive model. It's the same four independent")
    print("computations, run against the same programme, agreeing with each other.")


def chart_integrated_summary(d: dict, s: dict, c: dict, r: dict) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    ax = axes[0, 0]
    ts = d["ts"]
    actuals = dash.actuals_only(ts)
    ax.plot(ts["period_label"].to_numpy(), ts["planned_value_cum"].to_numpy(),
            label="Planned (PV)", color=SERIES_1, linewidth=2)
    ax.plot(actuals["period_label"].to_numpy(), actuals["earned_value_cum"].to_numpy(),
            label="Earned (EV)", color=SERIES_2, linewidth=2, marker="o", markersize=4)
    ax.plot(actuals["period_label"].to_numpy(), actuals["actual_cost_cum"].to_numpy(),
            label="Actual (AC)", color=SERIES_3, linewidth=2, marker="o", markersize=4)
    ax.set_title("Cost / EVM")
    ax.legend(fontsize=8)
    ax.grid(color=GRID, linewidth=0.6)
    ax.tick_params(axis="x", rotation=30)

    ax = axes[0, 1]
    comparison = s["comparison"]
    colors = {"CRITICAL": STATUS_CRITICAL, "near-critical": STATUS_WARNING, "ok": STATUS_GOOD}
    for i, row in enumerate(comparison.sort_values("current_start").itertuples()):
        tag = "CRITICAL" if row.is_critical else ("near-critical" if row.is_near_critical else "ok")
        start_num = mdates.date2num(row.current_start)
        width = mdates.date2num(row.current_finish) - start_num
        ax.barh(i, width, left=start_num, color=colors[tag], height=0.6)
    ax.set_yticks([])
    ax.set_title("Schedule (current, colored by criticality)")
    ax.xaxis_date()
    ax.tick_params(axis="x", rotation=30)

    ax = axes[1, 0]
    cum = c["cum"]
    ax.step(cum["date_decided"].to_numpy(), cum["cum_cost"].to_numpy(), where="post",
            color=SERIES_1, linewidth=2)
    ax.scatter(cum["date_decided"].to_numpy(), cum["cum_cost"].to_numpy(), color=SERIES_1, s=20)
    ax.axhline(0, color=INK, linewidth=0.8, alpha=0.6)
    ax.set_title("Cumulative Approved Change Cost")
    ax.grid(color=GRID, linewidth=0.6)
    ax.tick_params(axis="x", rotation=30)

    ax = axes[1, 1]
    trend = r["exposure_trend"]
    ax.plot(trend["snapshot_date"].to_numpy(), trend["total_exposure"].to_numpy(),
            color=SERIES_1, linewidth=2, marker="o")
    ax.set_title("Portfolio Risk Exposure")
    ax.grid(color=GRID, linewidth=0.6)
    ax.tick_params(axis="x", rotation=30)

    _apply_chrome(fig, axes)
    fig.suptitle("Ridgeline LNG Compressor Station Retrofit — Four Disciplines, One Programme",
                 fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "integrated_summary.png"), dpi=140, facecolor=CHART_BG)
    plt.close(fig)


def write_report_markdown(d: dict, s: dict, c: dict, r: dict) -> None:
    ds, ss, cs, rs = d["summary"], s["score"], c["stats"], r["score"]
    lines = [
        "# Integrated Programme Status Report",
        "",
        f"**Ridgeline LNG Compressor Station Retrofit** — as of {STATUS_DATE}",
        "",
        "| Discipline | Headline |",
        "|---|---|",
        f"| Cost / EVM | SPI {ds['spi']:.2f}, CPI {ds['cpi']:.2f}, EAC {money(ds['eac'])} |",
        f"| Schedule | Health Score {ss['total_score']}/100, slip {ss['slip_days']:+d}d |",
        f"| Change Control | Approved {money(cs['approved_cost_impact'])} ({cs['approved_schedule_days']:+d}d) |",
        f"| Risk | Trajectory Score {rs['total_score']}/100, exposure {rs['exposure_pct_change']:+.1f}% |",
        "",
        "## Integrated Observations",
        "",
        f"One root cause is visible independently across all four disciplines: the "
        f"compressor rotor procurement delay (activity P1, +30 days against baseline).",
        "",
        f"- **Schedule:** that single activity is the reason for the programme's entire "
        f"{ss['slip_days']}-day slip, and {ss['pct_activities_critical_or_near']}% of "
        f"activities are now critical or near-critical as a direct result.",
        f"- **Cost:** CPI has fallen to {ds['cpi']:.2f} over the same window the delay "
        f"unfolded, and {money(cs['approved_cost_impact'])} of the approved change impact "
        f"({cs['approved_schedule_days']:+d} net days) is the cost of responding to it, "
        f"chiefly the expedited air-freight change that clawed back schedule at a cost.",
        f"- **Risk:** the procurement-capacity risk (R01) was already flagged and "
        f"escalating months before the delay materialized, and its mitigation closed "
        f"after the risk had already converted into an actual schedule hit.",
        "",
        "No new predictive model. The same four independent computations, run against "
        "the same programme, agreeing with each other.",
        "",
    ]
    with open(os.path.join(ASSETS_DIR, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)

    d = run_dashboard_engine()
    s = run_schedule_engine()
    c = run_change_engine()
    r = run_risk_engine()

    print_report(d, s, c, r)
    chart_integrated_summary(d, s, c, r)
    write_report_markdown(d, s, c, r)

    print("-" * 68)
    print(f"Integrated chart and report.md saved to {ASSETS_DIR}")


if __name__ == "__main__":
    main()
