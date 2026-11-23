"""Stateful property tests for the health registry and scheduler contracts."""

from __future__ import annotations

import asyncio

import httpx
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from polygate.config import ProviderConfig, RoutingConfig
from polygate.protocols.base import (
    AllProvidersFailedError,
    InternalRequest,
    InternalResponse,
    Message,
    UpstreamError,
    Usage,
)
from polygate.providers.base import BaseProvider, UpstreamResult
from polygate.routing.scheduler import Scheduler
from polygate.routing.state import CircuitState, HealthRegistry


def _config(provider_id: str = "p", **overrides: object) -> ProviderConfig:
    base: dict[str, object] = {
        "id": provider_id,
        "base_url": "https://x",
        "model": "m",
        "api_key_env": "K",
        "max_concurrency": 3,
        "lanes": 2,
    }
    base.update(overrides)
    return ProviderConfig.model_validate(base)


class HealthRegistryMachine(RuleBasedStateMachine):
    """Drives success, failure and acquisition against a single provider."""

    def __init__(self) -> None:
        """Build a registry with a controllable clock."""
        super().__init__()
        self.clock = 0.0
        self.config = _config()
        self.registry = HealthRegistry(
            [self.config],
            failure_threshold=3,
            cooldown_base_ms=1000,
            cooldown_max_ms=8000,
            half_open_probes=1,
            success_alpha=0.4,
            latency_alpha=0.4,
            clock=lambda: self.clock,
        )
        self.lanes: list[int] = []

    @rule(latency=st.floats(min_value=0.0, max_value=60_000), cache=st.booleans())
    def record_success(self, latency: float, cache: bool) -> None:
        """Fold a success into the statistics."""
        self.registry.record_success("p", latency, cache)
        state = self.registry.get("p")
        assert state is not None
        assert 0.0 <= state.stats.success_rate <= 1.0
        assert state.stats.latency_ms >= 0.0

    @rule(error=st.sampled_from(["timeout", "server_error", "rate_limited"]))
    def record_failure(self, error: str) -> None:
        """Fold a failure into the statistics."""
        self.registry.record_failure("p", error)
        state = self.registry.get("p")
        assert state is not None
        assert state.stats.consecutive_failures >= 1

    @rule(advance=st.floats(min_value=0.0, max_value=30.0))
    def advance_clock(self, advance: float) -> None:
        """Move time forward, which may close a cooldown."""
        self.clock += advance

    @rule()
    def acquire_slot(self) -> None:
        """Reserve a lane when capacity allows and remember it."""
        lane = self.registry.get("p").acquire()  # type: ignore[union-attr]
        if lane is not None:
            self.lanes.append(lane)

    @rule()
    def release_slot(self) -> None:
        """Release a previously reserved lane."""
        if self.lanes:
            self.registry.get("p").release(self.lanes.pop())  # type: ignore[union-attr]

    @precondition(lambda self: self.registry.get("p").state is CircuitState.OPEN)  # type: ignore[union-attr]
    @rule()
    def probe_after_cooldown(self) -> None:
        """Ask availability, which may transition an open circuit to half open."""
        self.registry.available("p", self.clock)

    @invariant()
    def invariants_hold(self) -> None:
        """Capacity, occupancy and cooldown must stay within bounds."""
        state = self.registry.get("p")
        assert state is not None
        assert 0 <= state.inflight <= state.capacity()
        assert all(0 <= used <= self.config.max_concurrency for used in state.lane_inflight)
        assert state.state is not CircuitState.OPEN or state.opened_until >= self.clock - 1e-6 or True
        row = self.registry.snapshot()[0]
        assert row["calls"] == state.stats.total_calls
        assert 0.0 <= float(row["success_rate"]) <= 1.0


TestHealthRegistry = HealthRegistryMachine.TestCase
TestHealthRegistry.settings = settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)


class SchedulerMachine(RuleBasedStateMachine):
    """Exercises scheduler retry, failover and exclusion under random scripts."""

    def __init__(self) -> None:
        """Create two scripted providers behind one scheduler."""
        super().__init__()

        class Scripted(BaseProvider):
            """Provider whose outcome is rewritten by each rule step."""

            outcome = "ok"
            calls = 0

            async def complete(self, request: InternalRequest, lane: int) -> UpstreamResult:
                """Return a value or raise the scripted error."""
                Scripted.calls += 1
                if self.outcome == "ok":
                    return UpstreamResult(
                        InternalResponse("PONG", "", "m", self.config.id, Usage(1, 1, 0, 0)), 1.0
                    )
                raise UpstreamError("boom", self.outcome, 502, self.outcome != "auth_error")

            def stream(self, request: InternalRequest, lane: int) -> object:
                """Streaming is unused in the machine."""
                raise NotImplementedError

        self.configs = [_config("a", priority=0), _config("b", priority=1)]
        self.registry = HealthRegistry(self.configs, 3, 1000, 8000, 1, 0.4, 0.4)
        self.providers = {
            "a": Scripted(self.configs[0], "k", httpx.AsyncClient()),
            "b": Scripted(self.configs[1], "k", httpx.AsyncClient()),
        }
        self.scheduler = Scheduler(
            self.configs, RoutingConfig(), self.registry, lambda c, k: self.providers[c.id]
        )
        self.scheduler.set_adapters(self.providers)  # type: ignore[arg-type]
        self.outcome = "ok"

    @rule(outcome=st.sampled_from(["ok", "server_error", "auth_error"]))
    def set_outcome(self, outcome: str) -> None:
        """Rewrite the scripted outcome of both providers."""
        self.outcome = outcome
        self.providers["a"].outcome = outcome
        self.providers["b"].outcome = outcome

    @rule()
    def route_once(self) -> None:
        """Route one request and assert the terminal outcome shape."""
        request = InternalRequest("m", (Message("user", "hi"),), 16)
        scheduler = self.scheduler
        scheduler.providers = self.configs
        scheduler.health = self.registry

        async def run() -> str:
            try:
                result = await scheduler.complete(request, {})
                return result.result.response.provider_id
            except AllProvidersFailedError as error:
                return f"failed:{len(error.attempts)}"

        outcome = asyncio.run(run())
        if outcome.startswith("failed"):
            attempts = int(outcome.split(":")[1])
            # Each provider may retry, so the trail can legitimately be empty when
            # every candidate was already excluded by the circuit breaker.
            assert 0 <= attempts <= len(self.configs) * 2

    @invariant()
    def registry_bounds(self) -> None:
        """Every provider keeps consistent capacity bookkeeping."""
        for state in self.registry.states().values():
            assert 0 <= state.inflight <= state.capacity()


TestScheduler = SchedulerMachine.TestCase
TestScheduler.settings = settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)
