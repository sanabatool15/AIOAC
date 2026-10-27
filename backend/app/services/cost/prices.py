"""Single place for prices. PLACEHOLDERS: verify against current AWS pricing before the demo (specs/cost.md)."""
from dataclasses import dataclass

PRICES_VERSION = "placeholder-0"


@dataclass(frozen=True)
class InstanceSpec:
    hourly_cents: float        # PLACEHOLDER
    speed_factor: float        # cloud instance time / local sample time. Measure once per instance type.
    startup_seconds: float     # fixed job start + finish overhead. Measure.


INSTANCES = {"ml.m5.xlarge": InstanceSpec(hourly_cents=25.0, speed_factor=1.0, startup_seconds=240.0)}
DEFAULT_INSTANCE = "ml.m5.xlarge"
STORAGE_CENTS = 1
PLATFORM_FEE_CENTS = 50
