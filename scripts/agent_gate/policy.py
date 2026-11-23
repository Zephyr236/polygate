"""Load and apply the agent-gate decision policy."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):  # pragma: no branch
    import tomllib
else:  # pragma: no cover - scripts run on 3.12 in CI
    import tomli as tomllib  # type: ignore[no-redef]

ACCEPTANCE_LEVELS = {"auto", "human"}
ORACLES = {"rule", "pre_post", "fixture_command", "none"}


class PolicyError(ValueError):
    """Raised when a candidate or the policy file violates the contract."""


@dataclass(frozen=True)
class ArtifactSpec:
    """The contract for one artifact kind."""

    kind: str
    acceptance: str
    oracle: str
    paths: tuple[str, ...]
    requires: tuple[str, ...]


@dataclass(frozen=True)
class Policy:
    """The parsed decision policy."""

    version: int
    max_candidates: int
    gaps: dict[str, tuple[str, ...]]
    artifacts: dict[str, ArtifactSpec]

    def decide(self, gap_type: str, artifact: str) -> ArtifactSpec:
        """Return the artifact contract, or raise if the pairing is not allowed."""
        spec = self.artifacts.get(artifact)
        if spec is None:
            raise PolicyError(f"unknown artifact kind: {artifact}")
        allowed = self.gaps.get(gap_type)
        if allowed is None:
            raise PolicyError(f"unknown gap type: {gap_type}")
        if artifact not in allowed:
            raise PolicyError(
                f"artifact {artifact!r} is not allowed for gap type {gap_type!r}; allowed: {', '.join(allowed)}"
            )
        return spec

    def missing_fields(self, artifact: str, metadata: dict[str, Any]) -> list[str]:
        """Return required metadata fields that are absent or empty."""
        spec = self.artifacts[artifact]
        missing: list[str] = []
        for field in spec.requires:
            value = metadata.get(field)
            if not value:
                missing.append(field)
        return missing


def _parse_artifacts(raw: dict[str, Any]) -> dict[str, ArtifactSpec]:
    artifacts: dict[str, ArtifactSpec] = {}
    for kind, entry in raw.items():
        acceptance = str(entry.get("acceptance", ""))
        oracle = str(entry.get("oracle", ""))
        if acceptance not in ACCEPTANCE_LEVELS:
            raise PolicyError(f"artifact {kind!r} has invalid acceptance: {acceptance!r}")
        if oracle not in ORACLES:
            raise PolicyError(f"artifact {kind!r} has invalid oracle: {oracle!r}")
        paths = tuple(str(item) for item in entry.get("paths", []))
        requires = tuple(str(item) for item in entry.get("requires", []))
        if not paths or not requires:
            raise PolicyError(f"artifact {kind!r} needs non-empty paths and requires")
        artifacts[kind] = ArtifactSpec(kind, acceptance, oracle, paths, requires)
    return artifacts


def _parse_gaps(raw: dict[str, Any], artifacts: dict[str, ArtifactSpec]) -> dict[str, tuple[str, ...]]:
    gaps: dict[str, tuple[str, ...]] = {}
    for gap_type, entry in raw.items():
        listed = tuple(str(item) for item in entry.get("artifacts", []))
        if not listed:
            raise PolicyError(f"gap type {gap_type!r} has no artifacts")
        unknown = [item for item in listed if item not in artifacts]
        if unknown:
            raise PolicyError(f"gap type {gap_type!r} references unknown artifacts: {unknown}")
        gaps[gap_type] = listed
    return gaps


def load_policy(path: Path) -> Policy:
    """Load and validate the policy file."""
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PolicyError(f"policy file not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise PolicyError(f"invalid policy TOML in {path}: {error}") from error
    artifacts = _parse_artifacts(document.get("artifacts", {}))
    gaps = _parse_gaps(document.get("gap_types", {}), artifacts)
    version = int(document.get("version", 0))
    max_candidates = int(document.get("max_candidates", 20))
    if version < 1:
        raise PolicyError("policy version must be >= 1")
    if max_candidates < 1:
        raise PolicyError("max_candidates must be >= 1")
    return Policy(version, max_candidates, gaps, artifacts)


def ensure_inside(repo: Path, relative: str, prefixes: tuple[str, ...]) -> Path:
    """Resolve a repo-relative path and require it to sit under an allowed prefix."""
    if Path(relative).is_absolute():
        raise PolicyError(f"path must be repo-relative, absolute paths are not allowed: {relative}")
    resolved = (repo / relative).resolve()
    root = repo.resolve()
    if root not in resolved.parents and resolved != root:
        raise PolicyError(f"path escapes the repository: {relative}")
    allowed = [root / prefix for prefix in prefixes]
    if not any(path == resolved or path in resolved.parents for path in allowed):
        raise PolicyError(f"path {relative!r} is outside the allowed prefixes: {', '.join(prefixes)}")
    return resolved
