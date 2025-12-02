import os
import random
import time
from typing import Protocol, Optional

from metrics import EdgeMetrics


def _get_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class FaultModel(Protocol):
    """Interface for behavioral fault models. Called on each frame in MODE=twin."""

    def apply(self, metrics: EdgeMetrics) -> None:
        """
        Mutate the metrics in-place to simulate a fault.
        Called AFTER the base metrics have been computed.
        """
        ...


class MarkovStepper:
    """
    Minimal 3-state Markov chain to reflect multi-state reliability:
    Healthy ↔ Degraded ↔ Failed ↔ Recovering → Healthy.
    Transition probabilities are simple and time-homogeneous for now.
    """

    transitions = {
        "healthy": {"healthy": 0.9, "degraded": 0.1},
        "degraded": {"degraded": 0.75, "failed": 0.2, "recovering": 0.05},
        "failed": {"failed": 0.7, "recovering": 0.3},
        "recovering": {"recovering": 0.5, "healthy": 0.5},
    }

    def __init__(self, start_state: str = "healthy"):
        self.state = start_state

    def step(self) -> str:
        r = random.random()
        acc = 0.0
        for nxt, p in self.transitions[self.state].items():
            acc += p
            if r <= acc:
                self.state = nxt
                break
        return self.state


class NoFaultModel:
    """Default model: does nothing (used in MODE=real or twin without scenario)."""

    def apply(self, metrics: EdgeMetrics) -> None:
        return


class NetworkLikeFault:
    """
    Simulates intermittent network-like issues:
    - Bernoulli per frame: each frame can degrade with probability fail_p.
    - Poisson-ish bursts: burst_prob triggers a short burst window of degraded frames.
    - Degradation expressed as latency spikes and occasional unhealthy flag.
    C from table: detected via slow /status or non-200 caused by health flag.
    """

    def __init__(self, fail_p: float = 0.1, burst_prob: float = 0.05):
        self.fail_p = fail_p
        self.burst_prob = burst_prob
        self.burst_remaining = 0
        self._t_inject_set = False

    def apply(self, metrics: EdgeMetrics) -> None:
        # Mark first perturbation time
        if not self._t_inject_set:
            metrics.fault_active = True
            metrics.t_inject = time.time()
            self._t_inject_set = True

        # Start a burst with small probability
        if self.burst_remaining <= 0 and random.random() < self.burst_prob:
            self.burst_remaining = random.randint(5, 20)  # 5–20 frames degraded

        degraded = False
        if self.burst_remaining > 0:
            degraded = True
            self.burst_remaining -= 1
        elif random.random() < self.fail_p:
            degraded = True

        if degraded:
            metrics.queue_latency_ms *= random.uniform(1.5, 3.0)
            metrics.inference_ms *= random.uniform(1.5, 2.5)
            if random.random() < 0.2:
                metrics.healthy = False
                metrics.last_error = "simulated_network_timeout"
        else:
            metrics.healthy = True
            if metrics.last_error == "simulated_network_timeout":
                metrics.last_error = None


class CpuThrottleFault:
    """
    Simulates CPU starvation / thermal throttling:
    - Per-frame Bernoulli in main loop replaced by deterministic degradation (fps drop).
    - Represents Poisson spikes by multiplicative latency factor on each frame.
    """

    def __init__(self, drop_factor: float = 0.4, spike_lambda: float = 0.2):
        self.drop_factor = drop_factor
        self._t_inject_set = False
        self.spike_lambda = spike_lambda  # Poisson rate (events/sec)
        self.next_spike_ts: Optional[float] = None
        self.spike_remaining = 0

    def _schedule_spike(self, now: float) -> None:
        # Exponential inter-arrival to mimic Poisson CPU spikes
        wait = random.expovariate(self.spike_lambda)
        self.next_spike_ts = now + wait

    def apply(self, metrics: EdgeMetrics) -> None:
        if not self._t_inject_set:
            metrics.fault_active = True
            metrics.t_inject = time.time()
            self._t_inject_set = True
            self._schedule_spike(time.time())

        now = time.time()
        if self.next_spike_ts is None or now >= self.next_spike_ts:
            # start a spike window lasting a few frames
            self.spike_remaining = random.randint(3, 10)
            self._schedule_spike(now)

        if self.spike_remaining > 0:
            self.spike_remaining -= 1
            metrics.fps *= self.drop_factor
            metrics.queue_latency_ms *= random.uniform(1.5, 3.0)


class BlackFramesFault:
    """
    Simulates dead camera / black frames:
    - Bernoulli missing frames (fail_p) sets detection_rate to 0 and unhealthy flag.
    - Gap process is represented by intermittent failures rather than permanent ones.
    """

    def __init__(self, fail_p: float = 0.25):
        self.fail_p = fail_p
        self._t_inject_set = False

    def apply(self, metrics: EdgeMetrics) -> None:
        if not self._t_inject_set:
            metrics.fault_active = True
            metrics.t_inject = time.time()
            self._t_inject_set = True

        if random.random() < self.fail_p:
            metrics.detection_rate = 0.0
            metrics.healthy = False
            metrics.last_error = "simulated_black_frames"
        else:
            metrics.healthy = True
            if metrics.last_error == "simulated_black_frames":
                metrics.last_error = None


class CorruptedModelFault:
    """
    Simulates corrupted model weights:
    - Bernoulli corruption that increases over time (intermittent → failed).
    - Gradual degradation of detection_rate to mirror Markov-like drift to failure.
    """

    def __init__(self, base_fail_p: float = 0.05, growth: float = 0.02):
        self._t_inject_set = False
        self.base_fail_p = base_fail_p
        self.growth = growth
        self.steps = 0

    def apply(self, metrics: EdgeMetrics) -> None:
        if not self._t_inject_set:
            metrics.fault_active = True
            metrics.t_inject = time.time()
            self._t_inject_set = True
        self.steps += 1

        # Bernoulli fail probability grows over time (intermittent → failed)
        fail_p = min(1.0, self.base_fail_p + self.growth * self.steps)
        if random.random() < fail_p:
            metrics.healthy = False
            metrics.last_error = "model_load_error"
            metrics.fps = 0.0
            metrics.detection_rate = 0.0
        else:
            # Degrade detection rate gradually to reflect drift
            metrics.detection_rate = max(0.0, metrics.detection_rate * random.uniform(0.6, 0.9))
            metrics.inference_ms *= random.uniform(1.1, 1.5)


class DiskFullFault:
    """
    Simulates disk full / read-only filesystem:
    - Time-to-full ramp (exponential-like via ratio).
    - Bernoulli write failures that increase as disk fills.
    - Detection via unhealthy flag or elevated latency.
    """

    def __init__(self, time_to_full_sec: float = 90.0, base_fail_p: float = 0.05):
        self._t_inject_set = False
        self.time_to_full_sec = time_to_full_sec
        self.start_ts: Optional[float] = None
        self.base_fail_p = base_fail_p

    def apply(self, metrics: EdgeMetrics) -> None:
        if not self._t_inject_set:
            metrics.fault_active = True
            metrics.t_inject = time.time()
            self._t_inject_set = True
            self.start_ts = metrics.t_inject

        now = time.time()
        elapsed = now - (self.start_ts or now)
        fill_ratio = min(1.0, elapsed / self.time_to_full_sec)  # 0 → 1

        # Before full, increase latency proportional to fill_ratio
        metrics.queue_latency_ms *= (1.0 + fill_ratio)
        metrics.inference_ms *= (1.0 + 0.5 * fill_ratio)

        if fill_ratio >= 1.0:
            metrics.healthy = False
            metrics.last_error = "disk_full"
        else:
            # Bernoulli write failure increasing with fill_ratio
            fail_p = min(1.0, self.base_fail_p + fill_ratio * 0.5)
            if random.random() < fail_p:
                metrics.healthy = False
                metrics.last_error = "disk_write_error"
            else:
                metrics.healthy = True


class WrongArchFault:
    """
    Simulates wrong architecture rollout:
    - Deterministic failure with renewal attempts (retry loop).
    - We model retries by toggling between failed and recovering states.
    - Bernoulli retry success per cycle to exit failure, otherwise re-fail.
    """

    def __init__(self, retry_interval_sec: float = 20.0, fail_window_sec: float = 10.0, retry_success_p: float = 0.2):
        self._t_inject_set = False
        self.retry_interval_sec = retry_interval_sec
        self.fail_window_sec = fail_window_sec
        self.last_cycle_start: Optional[float] = None
        self.retry_success_p = retry_success_p

    def apply(self, metrics: EdgeMetrics) -> None:
        now = time.time()
        if not self._t_inject_set:
            metrics.fault_active = True
            metrics.t_inject = now
            self._t_inject_set = True
            self.last_cycle_start = now

        elapsed_cycle = now - (self.last_cycle_start or now)
        if elapsed_cycle <= self.fail_window_sec:
            # In fail window: app unhealthy as binary failure
            metrics.healthy = False
            metrics.last_error = "wrong_arch"
        else:
            # Recovering attempt window: slight degradation but healthy toggles true
            metrics.healthy = True
            metrics.queue_latency_ms *= 1.2
            metrics.inference_ms *= 1.2
            if elapsed_cycle >= self.retry_interval_sec:
                # Restart cycle to simulate repeated rollout attempts
                # Bernoulli success can end the fault
                if random.random() < self.retry_success_p:
                    metrics.healthy = True
                    metrics.last_error = None
                    return
                self.last_cycle_start = now
