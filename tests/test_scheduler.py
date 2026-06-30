"""Tests for signalpulse.scheduler (APScheduler-backed)."""
from __future__ import annotations

import pytest

from signalpulse.scheduler import (
    JobInfo,
    _parse_cron,
    add_job,
    list_jobs,
    remove_job,
    shutdown,
)


# ---- _parse_cron ----

def test_parse_cron_valid():
    """5-field cron -> {minute, hour, day, month, day_of_week}."""
    out = _parse_cron("0 9 * * 1")
    assert out == {"minute": "0", "hour": "9", "day": "*", "month": "*", "day_of_week": "1"}


def test_parse_cron_every_minute():
    """* * * * * should be parsed into asterisks."""
    out = _parse_cron("* * * * *")
    assert out == {"minute": "*", "hour": "*", "day": "*", "month": "*", "day_of_week": "*"}


def test_parse_cron_invalid_raises():
    """Non-5-field cron raises ValueError."""
    with pytest.raises(ValueError):
        _parse_cron("0 9 * *")  # only 4 fields


# ---- add_job / list_jobs / remove_job ----

@pytest.fixture
def _cleanup_scheduler():
    """Shutdown the scheduler after each test to avoid leaking threads."""
    yield
    try:
        shutdown()
    except Exception:  # noqa: BLE001
        pass


def test_add_job_returns_jobinfo(_cleanup_scheduler):
    """add_job returns a JobInfo dataclass with the right fields."""
    info = add_job(name="test_job_1", cron="0 9 * * 1", use_sample_dataset=True)
    assert isinstance(info, JobInfo)
    assert info.name == "test_job_1"
    assert info.cron == "0 9 * * 1"
    assert info.use_sample_dataset is True
    assert info.config_path == "configs/competitors.ai-agent.yaml"


def test_list_jobs_includes_added(_cleanup_scheduler):
    """list_jobs returns the job we just added."""
    add_job(name="test_list_xyz", cron="*/5 * * * *", use_sample_dataset=True)
    jobs = list_jobs()
    names = [j.name for j in jobs]
    assert "test_list_xyz" in names


def test_remove_job_returns_true(_cleanup_scheduler):
    """remove_job returns True for an existing job."""
    add_job(name="test_remove_me", cron="0 0 * * *", use_sample_dataset=True)
    assert remove_job("test_remove_me") is True
    # Second remove returns False
    assert remove_job("test_remove_me") is False


def test_remove_nonexistent_returns_false(_cleanup_scheduler):
    """remove_job returns False when the job doesn't exist."""
    assert remove_job("definitely_not_a_real_job_xyz") is False


def test_add_job_dedups_spaces_in_id(_cleanup_scheduler):
    """add_job replaces spaces in the name with underscores for the id."""
    info = add_job(name="my daily job", cron="0 0 * * *", use_sample_dataset=True)
    assert info.id == "my_daily_job"