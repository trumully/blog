"""Workspace-local deterministic family assignments for signature studies."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1
REGISTRY_FILENAME = "signature-registry.json"
LOCK_FILENAME = ".signature-registry.lock"
FAMILIES = ("ribbon-v1", "open-crescent", "open-hairpin")
_POST_PATH = re.compile(r"/posts/[a-z0-9]+(?:-[a-z0-9]+)*/\Z", re.ASCII)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RegistryError(Exception):
    """An invalid, unsafe, or inaccessible signature registry."""


class RegistryLockedError(RegistryError):
    """Another authoring process currently owns the registry lock."""


@dataclass(frozen=True)
class FamilyChoice:
    family: str
    status: str
    counts: dict[str, int]


@dataclass(frozen=True)
class Registry:
    assignments: dict[str, str]


def registry_path(workspace: Path) -> Path:
    return workspace / REGISTRY_FILENAME


def lock_path(workspace: Path) -> Path:
    return workspace / LOCK_FILENAME


def validate_canonical_path(canonical_path: str) -> None:
    if (
        not isinstance(canonical_path, str)
        or _POST_PATH.fullmatch(canonical_path) is None
    ):
        raise RegistryError(f"invalid registry post identity: {canonical_path!r}")


def _validate_workspace(workspace: Path, *, require_directory: bool) -> Path:
    workspace = Path(workspace)
    if not workspace.is_absolute():
        raise RegistryError("registry workspace must be absolute")
    if workspace.parent == workspace:
        raise RegistryError(
            f"registry workspace must not be a filesystem root: {workspace}"
        )
    if workspace.is_symlink():
        raise RegistryError(f"registry workspace must not be a symlink: {workspace}")
    resolved = workspace.resolve()
    if resolved != workspace:
        raise RegistryError(
            f"registry workspace must be resolved without symlink traversal: {workspace}"
        )
    if _is_relative_to(resolved, PROJECT_ROOT) or _is_relative_to(
        PROJECT_ROOT, resolved
    ):
        raise RegistryError(
            f"registry workspace must be separate from the blog repository: {resolved}"
        )
    if require_directory and (not workspace.exists() or not workspace.is_dir()):
        raise RegistryError(
            f"registry workspace must already exist as a directory: {workspace}"
        )
    if workspace.exists() and not workspace.is_dir():
        raise RegistryError(f"registry workspace is not a directory: {workspace}")
    return workspace


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _validate_assignments(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise RegistryError("signature registry assignments must be an object")
    assignments: dict[str, str] = {}
    for canonical_path, family in value.items():
        validate_canonical_path(canonical_path)
        if not isinstance(family, str) or family not in FAMILIES:
            raise RegistryError(f"invalid family for {canonical_path}: {family!r}")
        assignments[canonical_path] = family
    return assignments


def load_registry(workspace: Path) -> Registry:
    workspace = _validate_workspace(workspace, require_directory=False)
    path = registry_path(workspace)
    if path.is_symlink():
        raise RegistryError(f"signature registry must not be a symlink: {path}")
    if not path.exists():
        return Registry(assignments={})
    if not path.is_file():
        raise RegistryError(f"signature registry path is not a regular file: {path}")
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise RegistryError(f"cannot read signature registry {path}: {exc}") from exc
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data.get("schema_version") != SCHEMA_VERSION
    ):
        raise RegistryError(
            f"signature registry must be an object with schema_version {SCHEMA_VERSION}: {path}"
        )
    if set(data) != {"schema_version", "assignments"}:
        raise RegistryError(f"signature registry has unsupported fields: {path}")
    return Registry(assignments=_validate_assignments(data.get("assignments")))


def family_counts(assignments: dict[str, str]) -> dict[str, int]:
    validated = _validate_assignments(assignments)
    return {
        family: sum(1 for assigned in validated.values() if assigned == family)
        for family in FAMILIES
    }


def choose_family(canonical_path: str, assignments: dict[str, str]) -> FamilyChoice:
    validate_canonical_path(canonical_path)
    validated = _validate_assignments(assignments)
    counts = family_counts(validated)
    existing = validated.get(canonical_path)
    if existing is not None:
        return FamilyChoice(family=existing, status="assigned", counts=counts)

    least_used = min(counts.values())
    available = [family for family in FAMILIES if counts[family] == least_used]
    family = min(
        available,
        key=lambda candidate: (
            hashlib.sha256(
                b"signature-family-assignment-v1\0"
                + canonical_path.encode("ascii")
                + b"\0"
                + candidate.encode("ascii")
            ).digest(),
            candidate,
        ),
    )
    return FamilyChoice(family=family, status="proposed", counts=counts)


def save_registry(workspace: Path, registry: Registry) -> None:
    workspace = _validate_workspace(workspace, require_directory=True)
    path = registry_path(workspace)
    if path.is_symlink():
        raise RegistryError(f"signature registry must not be a symlink: {path}")
    if path.exists() and not path.is_file():
        raise RegistryError(f"signature registry path is not a regular file: {path}")
    assignments = _validate_assignments(registry.assignments)
    payload = {"schema_version": SCHEMA_VERSION, "assignments": assignments}
    temporary_path: Path | None = None
    temporary_identity: os.stat_result | None = None
    try:
        temporary_path = workspace / f".{REGISTRY_FILENAME}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(
            temporary_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
        )
        temporary_identity = os.fstat(descriptor)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as destination:
            json.dump(
                payload,
                destination,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        if path.is_symlink():
            raise RegistryError(
                f"signature registry became a symlink while saving: {path}"
            )
        os.replace(temporary_path, path)
        temporary_path = None
    except RegistryError:
        raise
    except OSError as exc:
        raise RegistryError(
            f"cannot atomically save signature registry {path}: {exc}"
        ) from exc
    finally:
        if temporary_path is not None and temporary_identity is not None:
            try:
                current = temporary_path.lstat()
                if (
                    not temporary_path.is_symlink()
                    and current.st_dev == temporary_identity.st_dev
                    and current.st_ino == temporary_identity.st_ino
                ):
                    temporary_path.unlink()
            except OSError:
                pass


@contextmanager
def registry_lock(workspace: Path) -> Iterator[None]:
    """Acquire an exclusive, fail-fast workspace lock; never remove an unowned lock."""
    workspace = _validate_workspace(workspace, require_directory=True)
    path = lock_path(workspace)
    if path.is_symlink():
        raise RegistryError(f"signature registry lock must not be a symlink: {path}")
    token = f"{os.getpid()}:{uuid.uuid4().hex}\n"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as exc:
        lock_collision = (
            isinstance(exc, FileExistsError) or path.exists() or path.is_symlink()
        )
        windows_exclusive_collision = isinstance(exc, PermissionError) and os.access(
            workspace, os.W_OK
        )
        if lock_collision or windows_exclusive_collision:
            raise RegistryLockedError(
                f"signature registry is locked: {path}; confirm no generator is active before removing a stale lock"
            ) from exc
        raise RegistryError(
            f"cannot create signature registry lock {path}: {exc}"
        ) from exc

    lock_stat = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as lock_file:
            lock_file.write(token)
            lock_file.flush()
            os.fsync(lock_file.fileno())
        yield
    finally:
        try:
            current = path.lstat()
            if (
                not path.is_symlink()
                and current.st_dev == lock_stat.st_dev
                and current.st_ino == lock_stat.st_ino
                and path.read_text(encoding="ascii") == token
            ):
                path.unlink()
        except OSError:
            pass


def assign_family(
    workspace: Path,
    canonical_path: str,
    *,
    before_save: Callable[[FamilyChoice], None] | None = None,
) -> FamilyChoice:
    """Choose and persist a new family under lock, running output preflight first."""
    workspace = _validate_workspace(workspace, require_directory=True)
    with registry_lock(workspace):
        registry = load_registry(workspace)
        choice = choose_family(canonical_path, registry.assignments)
        if before_save is not None:
            before_save(choice)
        if choice.status == "proposed":
            updated = dict(registry.assignments)
            updated[canonical_path] = choice.family
            save_registry(workspace, Registry(assignments=updated))
        return choice


__all__ = [
    "FAMILIES",
    "LOCK_FILENAME",
    "REGISTRY_FILENAME",
    "FamilyChoice",
    "Registry",
    "RegistryError",
    "RegistryLockedError",
    "assign_family",
    "choose_family",
    "family_counts",
    "load_registry",
    "lock_path",
    "registry_lock",
    "registry_path",
    "save_registry",
    "validate_canonical_path",
]
