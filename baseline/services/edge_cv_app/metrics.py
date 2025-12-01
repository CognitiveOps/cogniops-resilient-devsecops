from dataclasses import dataclass, asdict
from typing import Optional
import time


@dataclass
class EdgeMetrics:
    """
    Unified metrics structure for both real edge and digital twin.
    Returned by /status and consumed by S3 detector to compute MTTD / MTTR.
    """

    # Core CV pipeline signals
    fps: float = 0.0
    detection_rate: float = 0.0  # ratio [0,1]
    queue_latency_ms: float = 0.0
    inference_ms: float = 0.0

    # Health flags
    healthy: bool = True
    last_error: Optional[str] = None
    state: str = "healthy"  # multistate Markov: healthy/degraded/failed/recovering

    # Fault / scenario flags (for S3 twin mode)
    fault_active: bool = False
    t_inject: Optional[float] = None

    # Internal timing
    ts: float = 0.0
    frame_idx: int = 0

    def touch(self) -> None:
        """Update timestamp when metrics are refreshed."""
        self.ts = time.time()

    def to_dict(self) -> dict:
        """Serialize metrics to dictionary for JSON response."""
        return asdict(self)
