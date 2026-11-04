"""Backend settings, read from environment variables (see .env.example)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Exceeding any timeout triggers a fail-closed fallback (PRD §7.6).
    classifier_timeout_seconds: float = 3.0
    llm_timeout_seconds: float = 8.0
    validator_timeout_seconds: float = 3.0

    # Session context lives in memory only (D-008).
    session_max_turns: int = 6
    session_idle_timeout_seconds: float = 300.0

    # Only "fake" is supported until M2 and D-003.
    llm_provider_mode: str = "fake"

    # M1 development stand-in for device credentials (D-010). Unset means every request is
    # rejected.
    dev_device_token: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        defaults = cls()
        return cls(
            classifier_timeout_seconds=float(
                env.get("CLASSIFIER_TIMEOUT_SECONDS", defaults.classifier_timeout_seconds)
            ),
            llm_timeout_seconds=float(env.get("LLM_TIMEOUT_SECONDS", defaults.llm_timeout_seconds)),
            validator_timeout_seconds=float(
                env.get("VALIDATOR_TIMEOUT_SECONDS", defaults.validator_timeout_seconds)
            ),
            session_max_turns=int(env.get("SESSION_MAX_TURNS", defaults.session_max_turns)),
            session_idle_timeout_seconds=float(
                env.get("SESSION_IDLE_TIMEOUT_SECONDS", defaults.session_idle_timeout_seconds)
            ),
            llm_provider_mode=env.get("LLM_PROVIDER_MODE", defaults.llm_provider_mode),
            dev_device_token=env.get("DEV_DEVICE_TOKEN") or None,
        )
