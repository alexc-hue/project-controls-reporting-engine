"""Tests for reporting_engine.py.

Unlike the four standalone tools, this repo's engines/ are vendored copies
of already-tested logic, so a full duplicate test suite isn't the highest-
leverage use of effort here. This covers: _run_engine's error-wrapping (the
fix that turns a raw FileNotFoundError/KeyError traceback into a clear, named
SystemExit), _integrated_observations' composed narrative sentences, and one
smoke test per engine wrapper against the repo's own sample data (confirming
each still returns the expected dict shape).
"""

from __future__ import annotations

import pytest

import reporting_engine as engine


# --- _run_engine error-wrapping ---------------------------------------------

def test_run_engine_returns_result_on_success():
    result = engine._run_engine("dashboard", "some.csv", lambda: {"a": 1})
    assert result == {"a": 1}


def test_run_engine_wraps_file_not_found_as_named_system_exit():
    def boom():
        raise FileNotFoundError(2, "No such file or directory", "cost_schedule_timeseries.csv")

    with pytest.raises(SystemExit) as exc_info:
        engine._run_engine("dashboard", "cost_schedule_timeseries.csv", boom)
    message = str(exc_info.value)
    assert "dashboard" in message
    assert "cost_schedule_timeseries.csv" in message


def test_run_engine_wraps_key_error_as_named_system_exit():
    def boom():
        raise KeyError("earned_value_cum")

    with pytest.raises(SystemExit) as exc_info:
        engine._run_engine("dashboard", "cost_schedule_timeseries.csv", boom)
    message = str(exc_info.value)
    assert "dashboard" in message
    assert "earned_value_cum" in message


# --- _integrated_observations -----------------------------------------------

def test_integrated_observations_composes_expected_sentences():
    dash_summary = {"cpi": 0.87}
    sched_score = {"slip_days": 30, "pct_activities_critical_or_near": 40.0}
    chg_stats = {"approved_cost_impact": 53000, "approved_schedule_days": -10}

    obs = engine._integrated_observations(dash_summary, sched_score, chg_stats)

    assert "30-day slip" in obs.schedule
    assert "40.0%" in obs.schedule
    assert "0.87" in obs.cost
    assert "-10" in obs.cost or "-10 net days" in obs.cost
    assert obs.risk == engine.RISK_OBSERVATION


# --- smoke tests: each engine wrapper against the repo's own sample data ---

def test_run_dashboard_engine_smoke():
    result = engine.run_dashboard_engine()
    assert set(result.keys()) == {
        "ts", "milestones", "risks", "changes", "summary", "forecast_finish", "change_summary",
    }
    assert "spi" in result["summary"]


def test_run_schedule_engine_smoke():
    result = engine.run_schedule_engine()
    assert set(result.keys()) == {"baseline", "current", "comparison", "score"}
    assert "total_score" in result["score"]


def test_run_change_engine_smoke():
    result = engine.run_change_engine()
    assert set(result.keys()) == {"changes", "cum", "stats"}
    assert "approval_rate_pct" in result["stats"]


def test_run_risk_engine_smoke():
    result = engine.run_risk_engine()
    assert set(result.keys()) == {"exposure_trend", "trajectory", "effectiveness", "score"}
    assert "total_score" in result["score"]
