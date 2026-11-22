"""The capability model shared by every NebulaOS hardware backend.

A feature is never reported as simply "supported". Each capability records
five separate facts, in order, so a front end can show exactly how far along
it is:

  hardware   the hardware can do it (from IDs, EDID, specs)
  driver     a driver / software stack for it is installed and loaded
  available  the system exposes it and it could be used now
  enabled    it is currently switched on
  verified   it was actually exercised and worked (e.g. a probe succeeded)

Each fact is True, False or None (unknown: never guessed). `evidence` says
where every fact came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

LEVELS = ("hardware", "driver", "available", "enabled", "verified")

# Wording when the next level is known to be False.
_STOPPED_AT = {
    "hardware": "hardware capable, no working driver",
    "driver": "driver present, not available",
    "available": "available, turned off",
    "enabled": "enabled, verification failed",
}
# Wording when the next level is unknown.
_REACHED = {
    "hardware": "hardware capable",
    "driver": "driver present",
    "available": "available",
    "enabled": "enabled",
}


@dataclass
class Capability:
    id: str
    label: str
    hardware: Optional[bool] = None
    driver: Optional[bool] = None
    available: Optional[bool] = None
    enabled: Optional[bool] = None
    verified: Optional[bool] = None
    evidence: List[str] = field(default_factory=list)

    def level(self) -> Optional[str]:
        """Highest level reached by an unbroken chain of True facts.
        Unknown (None) facts do not break the chain."""
        reached = None
        for name in LEVELS:
            value = getattr(self, name)
            if value is False:
                break
            if value is True:
                reached = name
        return reached

    def status(self) -> str:
        if self.hardware is False:
            return "not supported by the hardware"
        level = self.level()
        if level is None:
            first_false = next((n for n in LEVELS if getattr(self, n) is False), None)
            return f"not available ({first_false} missing)" if first_false else "unknown"
        if level == "verified":
            return "verified working"
        nxt = LEVELS[LEVELS.index(level) + 1]
        if getattr(self, nxt) is False:
            return _STOPPED_AT[level]
        return f"{_REACHED[level]} (not verified)" if level == "enabled" else f"{_REACHED[level]} ({nxt}: unknown)"

    def to_dict(self) -> Dict[str, object]:
        data: Dict[str, object] = {"id": self.id, "label": self.label}
        for name in LEVELS:
            data[name] = getattr(self, name)
        data["level"] = self.level()
        data["status"] = self.status()
        data["evidence"] = list(self.evidence)
        return data


@dataclass
class Note:
    """A compatibility observation for the user. `level` is ok, info, warn or fail."""

    level: str
    message: str
    subject: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {"level": self.level, "subject": self.subject, "message": self.message}
