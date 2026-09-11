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
from typing import Callable, NamedTuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from engines import chart_style
from engines.dashboard import metrics as dash_metrics
from engines.schedule import metrics as sched_metrics
from engines.change import metrics as chg_metrics
from engines.risk import metrics as risk_metrics
from engines.formatting import money

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

# Edit these to match your own programme -- see README ("point this at your
# own data"). They aren't read from the CSVs: BAC/PROJECT_START/
# PLANNED_FINISH/STATUS_DATE are this fictional programme's assumptions, and
# swapping in your own CSVs without also updating these will compute a real
# programme against the wrong budget, dates, and status cutoff.
BAC = 2_400_000
PROJECT_START = "2026-01-05"
PLANNED_FINISH = "2026-08-03"
STATUS_DATE = "2026-08-01"


def run_dashboard_engine():
    ts = dash_metrics.load_timeseries(os.path.join(DATA_DIR, "cost_schedule_timeseries.csv"))
    milestones = dash_metrics.load_milestones(os.path.join(DATA_DIR, "milestones.csv"))
    risks = dash_metrics.load_risk_register(os.path.join(DATA_DIR, "risk_register.csv"), STATUS_DATE)
    changes = dash_metrics.load_change_register(os.path.join(DATA_DIR, "change_register.csv"))
    summary = dash_metrics.project_summary(ts, BAC)
    forecast_finish = dash_metrics.forecast_completion_date(summary["spi"], PROJECT_START, PLANNED_FINISH)
    change_summary = dash_metrics.change_impact_summary(changes, BAC)
    return {
        "ts": ts, "milestones": milestones, "risks": risks, "changes": changes,
        "summary": summary, "forecast_finish": forecast_finish, "change_summary": change_summary,
    }


def run_schedule_engine():
    activities = sched_metrics.load_activities(os.path.join(DATA_DIR, "activities.csv"))
    baseline, current = sched_metrics.run_baseline_and_current(activities, PROJECT_START)
    comparison = sched_metrics.compare_schedules(activities, baseline, current)
    score = sched_metrics.schedule_health_score(comparison, baseline.project_finish, current.project_finish)
    return {"baseline": baseline, "current": current, "comparison": comparison, "score": score}


def run_change_engine():
    raw = chg_metrics.load_change_log(os.path.join(DATA_DIR, "change_log.csv"))
    changes = chg_metrics.add_cycle_and_aging(raw, STATUS_DATE)
    cum = chg_metrics.cumulative_impact(changes)
    stats = chg_metrics.summary_stats(changes)
    return {"changes": changes, "cum": cum, "stats": stats}


def run_risk_engine():
    snapshots = risk_metrics.load_snapshots(os.path.join(DATA_DIR, "risk_snapshots.csv"))
    exposure_trend = risk_metrics.portfolio_exposure_trend(snapshots)
    latest = snapshots["snapshot_date"].max()
    trajectory = risk_metrics.per_risk_trajectory(snapshots, latest)
    effectiveness = risk_metrics.mitigation_effectiveness(snapshots)
    score = risk_metrics.risk_trajectory_score(effectiveness, snapshots)
    return {"exposure_trend": exposure_trend, "trajectory": trajectory,
            "effectiveness": effectiveness, "score": score}


def _run_engine(label: str, files_needed: str, fn: Callable[[], dict]) -> dict:
    """Run one engine, turning a missing/malformed data file into a clear,
    named error instead of letting a raw traceback abort the whole report
    even though the other three engines may well have already succeeded."""
    try:
        return fn()
    except FileNotFoundError as exc:
        raise SystemExit(
            f"Cannot build the integrated report: the {label} engine couldn't find "
            f"{exc.filename!r}. Needs: {files_needed} in {DATA_DIR}. See the README "
            f"for what each engine's CSV(s) require."
        ) from exc
    except KeyError as exc:
        raise SystemExit(
            f"Cannot build the integrated report: the {label} engine's data is missing "
            f"an expected column ({exc}). Needs: {files_needed} in {DATA_DIR}, with the "
            f"same columns as the standalone tool's README describes."
        ) from exc


class IntegratedObservations(NamedTuple):
    schedule: str
    cost: str
    risk: str


# Fixed narrative, not computed from any run's data: this programme's risk
# register genuinely did flag R01 (procurement capacity) well before the
# delay landed, so this observation doesn't need to be dynamic the way the
# schedule/cost ones do.
RISK_OBSERVATION = (
    "the procurement-capacity risk (R01) was already flagged and "
    "escalating months before the delay materialized, and its mitigation "
    "closed after the risk had already converted into an actual schedule "
    "hit, a live example of exactly what a risk register tracked as a trend "
    "is supposed to catch, and a single snapshot would have missed."
)


def _forecast_str(forecast_finish) -> str:
    return forecast_finish.strftime("%Y-%m-%d") if forecast_finish is not None else "not yet forecastable"


def _integrated_observations(dash_summary: dict, sched_score: dict, chg_stats: dict) -> IntegratedObservations:
    """The schedule/cost observation sentences, shared by the console report
    and the markdown writer so they can't drift out of sync with each other
    -- they had drifted before, when the markdown version silently dropped a
    clause the console version kept."""
    schedule_obs = (
        f"that single activity is the reason for the programme's entire "
        f"{sched_score['slip_days']}-day slip, and {sched_score['pct_activities_critical_or_near']}% "
        f"of activities are now critical or near-critical as a direct result."
    )
    cost_obs = (
        f"CPI has fallen to {dash_summary['cpi']:.2f} over the same window the delay "
        f"unfolded, and {money(chg_stats['approved_cost_impact'])} of the approved change "
        f"impact ({chg_stats['approved_schedule_days']:+d} net days) is the cost of "
        f"responding to it, chiefly the expedited air-freight change that clawed "
        f"back schedule at a cost."
    )
    return IntegratedObservations(schedule_obs, cost_obs, RISK_OBSERVATION)


def print_report(dash: dict, sched: dict, chg: dict, rsk: dict, obs: IntegratedObservations) -> None:
    dash_summary, sched_score, chg_stats, risk_score = dash["summary"], sched["score"], chg["stats"], rsk["score"]

    print("=" * 68)
    print("INTEGRATED PROGRAMME STATUS REPORT")
    print("Ridgeline LNG Compressor Station Retrofit — as of", STATUS_DATE)
    print("=" * 68)
    print()
    forecast_finish, change_summary = dash["forecast_finish"], dash["change_summary"]
    forecast_str = _forecast_str(forecast_finish)

    print("COST / EVM (dashboard engine)")
    print(f"  SPI {dash_summary['spi']:.2f}  CPI {dash_summary['cpi']:.2f}  EAC {money(dash_summary['eac'])}  "
          f"VAC {money(dash_summary['vac'])}")
    print(f"  SPI-based forecast finish: {forecast_str}   "
          f"Revised budget (BAC + approved changes): {money(change_summary['revised_budget'])}")
    print()
    print("SCHEDULE (schedule health engine)")
    print(f"  Schedule Health Score: {sched_score['total_score']}/100  "
          f"Slip: {sched_score['slip_days']:+d}d  "
          f"Critical/near-critical: {sched_score['pct_activities_critical_or_near']}%")
    print()
    print("CHANGE CONTROL (change engine)")
    print(f"  Approved: {money(chg_stats['approved_cost_impact'])}  "
          f"({chg_stats['approved_schedule_days']:+d}d)   "
          f"Pending: {money(chg_stats['pending_cost_exposure'])}   "
          f"Stale pending: {chg_stats['stale_pending_count']}")
    print()
    print("RISK (risk trend engine)")
    print(f"  Risk Trajectory Score: {risk_score['total_score']}/100  "
          f"Effective mitigations: {risk_score['effective_mitigations']}/{risk_score['assessable_mitigations']}")
    print(f"  Exposure change: {risk_score['shared_exposure_pct_change']:+.1f}% (shared-risk basis for the "
          f"score above; raw incl. register churn: {risk_score['exposure_pct_change']:+.1f}%)")

    print()
    print("-" * 68)
    print("INTEGRATED OBSERVATIONS")
    print("-" * 68)
    print()
    print("One root cause is visible independently across all four disciplines: the")
    print("compressor rotor procurement delay (activity P1, +30 days against baseline).")
    print()
    print(f"  - Schedule: {obs.schedule}")
    print()
    print(f"  - Cost: {obs.cost}")
    print()
    print(f"  - Risk: {obs.risk}")
    print()
    print("None of this is a new predictive model. It's the same four independent")
    print("computations, run against the same programme, agreeing with each other.")


def chart_integrated_summary(dash: dict, sched: dict, chg: dict, rsk: dict) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))

    ax = axes[0, 0]
    ts = dash["ts"]
    actuals = dash_metrics.actuals_only(ts)
    ax.plot(ts["period_label"].to_numpy(), ts["planned_value_cum"].to_numpy(),
            label="Planned (PV)", color=chart_style.SERIES_1, linewidth=2)
    ax.plot(actuals["period_label"].to_numpy(), actuals["earned_value_cum"].to_numpy(),
            label="Earned (EV)", color=chart_style.SERIES_2, linewidth=2, marker="o", markersize=4)
    ax.plot(actuals["period_label"].to_numpy(), actuals["actual_cost_cum"].to_numpy(),
            label="Actual (AC)", color=chart_style.SERIES_3, linewidth=2, marker="o", markersize=4)
    ax.set_title("Cost / EVM")
    ax.legend(fontsize=8)
    ax.grid(color=chart_style.GRID, linewidth=0.6)
    ax.tick_params(axis="x", rotation=30)

    ax = axes[0, 1]
    comparison = sched["comparison"]
    colors = {"CRITICAL": chart_style.STATUS_CRITICAL, "near-critical": chart_style.STATUS_WARNING,
              "ok": chart_style.STATUS_GOOD}
    for i, row in enumerate(comparison.sort_values("current_start").itertuples()):
        tag = "CRITICAL" if row.is_critical else ("near-critical" if row.is_near_critical else "ok")
        start_num = mdates.date2num(row.current_start)
        width = mdates.date2num(row.current_finish) - start_num
        ax.barh(i, width, left=start_num, color=colors[tag], height=0.6)
    ax.set_yticks([])
    ax.set_title("Schedule (current, colored by criticality)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, label=k) for k, c in colors.items()]
    ax.legend(handles=handles, loc="lower right", fontsize=7)
    ax.xaxis_date()
    ax.tick_params(axis="x", rotation=30)

    ax = axes[1, 0]
    cum = chg["cum"]
    ax.step(cum["date_decided"].to_numpy(), cum["cum_cost"].to_numpy(), where="post",
            color=chart_style.SERIES_1, linewidth=2)
    ax.scatter(cum["date_decided"].to_numpy(), cum["cum_cost"].to_numpy(), color=chart_style.SERIES_1, s=20)
    ax.axhline(0, color=chart_style.INK, linewidth=0.8, alpha=0.6)
    ax.set_title("Cumulative Approved Change Cost")
    ax.grid(color=chart_style.GRID, linewidth=0.6)
    ax.tick_params(axis="x", rotation=30)

    ax = axes[1, 1]
    trend = rsk["exposure_trend"]
    ax.plot(trend["snapshot_date"].to_numpy(), trend["total_exposure"].to_numpy(),
            color=chart_style.SERIES_1, linewidth=2, marker="o")
    ax.set_title("Portfolio Risk Exposure")
    ax.grid(color=chart_style.GRID, linewidth=0.6)
    ax.tick_params(axis="x", rotation=30)

    chart_style.apply_chrome(fig, axes)
    fig.suptitle("Ridgeline LNG Compressor Station Retrofit — Four Disciplines, One Programme",
                 fontsize=13, color=chart_style.INK)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "integrated_summary.png"), dpi=140, facecolor=chart_style.CHART_BG)
    plt.close(fig)


def write_report_markdown(dash: dict, sched: dict, chg: dict, rsk: dict, obs: IntegratedObservations) -> None:
    dash_summary, sched_score, chg_stats, risk_score = dash["summary"], sched["score"], chg["stats"], rsk["score"]
    forecast_finish, change_summary = dash["forecast_finish"], dash["change_summary"]
    forecast_str = _forecast_str(forecast_finish)
    lines = [
        "# Integrated Programme Status Report",
        "",
        f"**Ridgeline LNG Compressor Station Retrofit** — as of {STATUS_DATE}",
        "",
        "| Discipline | Headline |",
        "|---|---|",
        f"| Cost / EVM | SPI {dash_summary['spi']:.2f}, CPI {dash_summary['cpi']:.2f}, EAC {money(dash_summary['eac'])} |",
        f"| Forecast (SPI-based) | Finish {forecast_str}, revised budget {money(change_summary['revised_budget'])} |",
        f"| Schedule | Health Score {sched_score['total_score']}/100, slip {sched_score['slip_days']:+d}d |",
        f"| Change Control | Approved {money(chg_stats['approved_cost_impact'])} ({chg_stats['approved_schedule_days']:+d}d) |",
        f"| Risk | Trajectory Score {risk_score['total_score']}/100, exposure {risk_score['shared_exposure_pct_change']:+.1f}% "
        f"(basis for score; raw incl. churn {risk_score['exposure_pct_change']:+.1f}%) |",
        "",
        "## Integrated Observations",
        "",
        f"One root cause is visible independently across all four disciplines: the "
        f"compressor rotor procurement delay (activity P1, +30 days against baseline).",
        "",
        f"- **Schedule:** {obs.schedule}",
        f"- **Cost:** {obs.cost}",
        f"- **Risk:** {obs.risk}",
        "",
        "No new predictive model. The same four independent computations, run against "
        "the same programme, agreeing with each other.",
        "",
    ]
    with open(os.path.join(ASSETS_DIR, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)

    dash_result = _run_engine(
        "dashboard", "cost_schedule_timeseries.csv, milestones.csv, risk_register.csv, change_register.csv",
        run_dashboard_engine,
    )
    sched_result = _run_engine("schedule", "activities.csv", run_schedule_engine)
    chg_result = _run_engine("change", "change_log.csv", run_change_engine)
    rsk_result = _run_engine("risk", "risk_snapshots.csv", run_risk_engine)
    obs = _integrated_observations(dash_result["summary"], sched_result["score"], chg_result["stats"])

    print_report(dash_result, sched_result, chg_result, rsk_result, obs)
    chart_integrated_summary(dash_result, sched_result, chg_result, rsk_result)
    write_report_markdown(dash_result, sched_result, chg_result, rsk_result, obs)

    print("-" * 68)
    print(f"Integrated chart and report.md saved to {ASSETS_DIR}")


if __name__ == "__main__":
    main()
