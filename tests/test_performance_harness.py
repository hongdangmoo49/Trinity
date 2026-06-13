from __future__ import annotations

from tests.harness.perf import (
    create_workflow_perf_fixture,
    measure_ms,
    snapshot_probe,
)


def test_workflow_perf_fixture_generates_scalable_state(tmp_path) -> None:
    fixture = create_workflow_perf_fixture(
        tmp_path,
        package_count=8,
        event_count=25,
        review_result_count=12,
        shared_bytes=4096,
    )

    assert fixture.session_path.exists()
    assert fixture.events_path.exists()
    assert fixture.config.shared_context_path.stat().st_size == 4096
    assert len(fixture.session.work_packages) == 8
    assert len(fixture.session.execution_results) == 7
    assert len(fixture.session.review_results) == 12

    loaded = fixture.persistence.load()
    assert loaded is not None
    assert loaded.id == "wf-perf"
    assert len(fixture.persistence.load_events_for_workflow("wf-perf")) == 25


def test_workflow_perf_fixture_supports_snapshot_timing_probe(tmp_path) -> None:
    fixture = create_workflow_perf_fixture(
        tmp_path,
        package_count=12,
        event_count=100,
        review_result_count=30,
        shared_bytes=8192,
    )

    stats, snapshot = measure_ms(lambda: snapshot_probe(fixture), repeat=3)

    assert stats.count == 3
    assert 0 <= stats.min_ms <= stats.avg_ms <= stats.max_ms
    assert snapshot.session_id == "wf-perf"
    assert snapshot.state == "executing"
    assert len(snapshot.work_packages) == 12
    assert snapshot.execution_recovery is not None


def test_workflow_perf_fixture_can_measure_event_load(tmp_path) -> None:
    fixture = create_workflow_perf_fixture(
        tmp_path,
        package_count=5,
        event_count=250,
        review_result_count=5,
    )

    stats, events = measure_ms(
        lambda: fixture.persistence.load_events_for_workflow("wf-perf"),
        repeat=3,
    )

    assert stats.count == 3
    assert len(events) == 250

