"""Testes: Circuit Breaker, Tool Registry V2, Health Check."""

import time

import pytest

from app.core.orchestrator.circuit_breaker import CircuitBreaker, CircuitState
from app.core.tool_registry import (
    ToolExecutionStats,
    by_permission,
    by_tag,
    discover,
    get,
    registry_summary,
    reset_registry,
    tool,
)

# ── CircuitBreaker ──────────────────────────────────────────────


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow() is False

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.allow() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_success_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05, success_threshold=1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.1)
        cb.allow()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.1)
        cb.allow()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_resets_failure_count_on_success(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0

    def test_to_dict(self):
        cb = CircuitBreaker()
        d = cb.to_dict()
        assert d["state"] == "closed"
        assert d["failure_threshold"] == 3


# ── ToolExecutionStats ──────────────────────────────────────────


class TestToolExecutionStats:
    def test_initial_state(self):
        s = ToolExecutionStats()
        assert s.total_calls == 0
        assert s.success_rate == 0.0
        assert s.avg_duration_ms == 0.0

    def test_record_success(self):
        s = ToolExecutionStats()
        s.record_success(100.0)
        assert s.total_calls == 1
        assert s.success_count == 1
        assert s.success_rate == 1.0
        assert s.avg_duration_ms == 100.0

    def test_record_failure(self):
        s = ToolExecutionStats()
        s.record_failure("err", 50.0)
        assert s.total_calls == 1
        assert s.failure_count == 1
        assert s.last_error == "err"

    def test_mixed(self):
        s = ToolExecutionStats()
        s.record_success(100.0)
        s.record_success(200.0)
        s.record_failure("x", 50.0)
        assert s.total_calls == 3
        assert s.success_rate == pytest.approx(2 / 3, abs=0.01)
        assert s.avg_duration_ms == pytest.approx(150.0, abs=1)

    def test_to_dict(self):
        s = ToolExecutionStats()
        s.record_success(100.0)
        d = s.to_dict()
        assert d["total_calls"] == 1
        assert d["success_rate"] == 1.0


# ── Tool Registry V2 ───────────────────────────────────────────


class TestToolRegistryV2:
    def setup_method(self):
        reset_registry()

    def test_tool_decorator_with_version_and_tags(self):
        @tool(
            name="test_v2_tool",
            description="A test tool",
            parameters={"q": {"type": "string"}},
            version="2.0.0",
            tags=["test", "math"],
        )
        def handler(args):
            return "ok"

        t = get("test_v2_tool")
        assert t is not None
        assert t.version == "2.0.0"
        assert "test" in t.tags
        assert "math" in t.tags

    def test_by_tag(self):
        @tool(name="tag_a", description="a", parameters={}, tags=["alpha"])
        def h1(a): return ""
        @tool(name="tag_b", description="b", parameters={}, tags=["beta"])
        def h2(a): return ""
        @tool(name="tag_c", description="c", parameters={}, tags=["alpha"])
        def h3(a): return ""

        alpha = by_tag("alpha")
        assert len(alpha) == 2

    def test_by_permission(self):
        @tool(name="perm_tool", description="d", parameters={}, permission="screen")
        def h(a): return ""

        tools = by_permission("screen")
        assert len(tools) == 1

    def test_discover_by_query(self):
        @tool(name="search_web", description="Search the web", parameters={})
        def h(a): return ""

        results = discover(query="web")
        assert len(results) == 1

    def test_discover_by_tag_and_permission(self):
        @tool(name="disc_tool", description="d", parameters={}, permission="screen", tags=["capture"])
        def h(a): return ""

        results = discover(tag="capture")
        assert len(results) == 1
        results = discover(permission="screen")
        assert len(results) == 1

    def test_tool_to_dict(self):
        @tool(name="dict_tool", description="d", parameters={}, version="3.0.0", tags=["x"])
        def h(a): return ""

        t = get("dict_tool")
        d = t.to_dict()
        assert d["version"] == "3.0.0"
        assert d["tags"] == ["x"]
        assert "stats" in d

    def test_registry_summary(self):
        @tool(name="sum_tool", description="s", parameters={})
        def h(a): return ""

        s = registry_summary()
        assert s["total"] >= 1
        assert "sum_tool" in s["names"]


# ── Health Check ────────────────────────────────────────────────


class TestHealthCheck:
    def test_check_tool_registry(self):
        from app.core.health import check_tool_registry
        result = check_tool_registry()
        assert result.name == "tool_registry"
        assert result.status == "ok"

    def test_check_database(self):
        from app.core.health import check_database
        result = check_database()
        assert result.name == "database"
        assert result.status == "ok"

    def test_full_health_check(self):
        from app.core.health import full_health_check
        report = full_health_check()
        assert report.status in ("ok", "degraded", "error")
        assert len(report.components) >= 3
        d = report.to_dict()
        assert "components" in d
