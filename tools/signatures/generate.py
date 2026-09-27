# /// script
# requires-python = "==3.13.*"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recipe import make_recipe
from registry import (
    FAMILIES,
    FamilyChoice,
    RegistryError,
    assign_family,
    choose_family,
    load_registry,
    registry_path,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
THREADS = 4
DEFAULT_TIMEOUT_SECONDS = 1200
BLENDER_VERSION_TIMEOUT_SECONDS = 30
QUALITY_OUTPUTS = (
    "latte.png",
    "mocha.png",
    "latte.blend",
    "mocha.blend",
    "manifest.json",
)
GENERATED_FILES = ("job.json", "blender.log", *QUALITY_OUTPUTS)
BACKGROUND_MODES = ("theme", "transparent")
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)
RECIPE_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*", re.ASCII)
HEX_SEED_PATTERN = re.compile(r"[0-9a-fA-F]+", re.ASCII)


class UserInputError(Exception):
    """An invalid command or unsafe output request."""


class RenderError(Exception):
    """A Blender discovery, execution, or output-validation failure."""


@dataclass(frozen=True)
class JobPlan:
    slug: str
    canonical_path: str
    variation: int
    quality: str
    recipe: dict[str, Any]
    workspace: Path
    output_dir: Path
    scene_path: Path
    project_root: Path
    background: str = "theme"

    @property
    def job_path(self) -> Path:
        return self.output_dir / "job.json"

    @property
    def log_path(self) -> Path:
        return self.output_dir / "blender.log"

    @property
    def manifest_path(self) -> Path:
        return self.output_dir / "manifest.json"


def parse_nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a nonnegative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return parsed


def parse_positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an isolated, deterministic Latte/Mocha Blender signature study for an existing blog post."
    )
    parser.add_argument("slug", help="existing ASCII post slug from src/blog/<slug>.md")
    parser.add_argument(
        "--quality",
        choices=("preview", "final"),
        default="preview",
        help="render quality (default: preview)",
    )
    parser.add_argument(
        "--background",
        choices=BACKGROUND_MODES,
        default="theme",
        help="background output mode (default: theme)",
    )
    parser.add_argument(
        "--variation",
        type=parse_nonnegative_int,
        default=0,
        help="reproducible alternate candidate number (default: 0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the recipe, paths, and Blender command without writing or launching Blender",
    )
    parser.add_argument(
        "--blender",
        metavar="PATH",
        help="Blender executable (otherwise BLENDER_EXE, PATH, and standard install locations are checked)",
    )
    parser.add_argument(
        "--workspace",
        metavar="PATH",
        help="study output workspace (default: SIGNATURE_WORKSPACE or ~/art-studies/blog-signatures)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace known outputs in a matching generated job; unrelated files are preserved",
    )
    parser.add_argument(
        "--timeout",
        type=parse_positive_int,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=f"render process timeout (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    return parser


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _assert_workspace_isolated(workspace: Path, project_root: Path) -> None:
    if workspace.parent == workspace:
        raise UserInputError(f"workspace must not be a filesystem root: {workspace}")
    if _is_relative_to(workspace, project_root) or _is_relative_to(
        project_root, workspace
    ):
        raise UserInputError(
            f"workspace must be separate from the blog repository (not inside it or an ancestor of it): {workspace}"
        )
    if workspace.exists() and not workspace.is_dir():
        raise UserInputError(f"workspace exists but is not a directory: {workspace}")


def resolve_workspace(
    requested: str | Path | None, project_root: Path = PROJECT_ROOT
) -> Path:
    if requested is not None:
        workspace_value = requested
    else:
        workspace_value = os.environ.get("SIGNATURE_WORKSPACE") or (
            Path.home() / "art-studies" / "blog-signatures"
        )
    workspace = Path(workspace_value).expanduser().resolve()
    root = project_root.resolve()
    _assert_workspace_isolated(workspace, root)
    return workspace


def resolve_post(slug: str, project_root: Path = PROJECT_ROOT) -> tuple[Path, str]:
    if not slug.isascii() or SLUG_PATTERN.fullmatch(slug) is None:
        raise UserInputError(
            "post slug must contain only lowercase ASCII letters, digits, and single hyphens"
        )

    root = project_root.resolve()
    blog_root = (root / "src" / "blog").resolve()
    post_path = blog_root / f"{slug}.md"
    if not post_path.is_file():
        raise UserInputError(f"no existing post found for slug {slug!r}: {post_path}")
    if not _is_relative_to(post_path.resolve(), blog_root):
        raise UserInputError(
            f"post file resolves outside src/blog and cannot be used: {post_path}"
        )
    return post_path, f"/posts/{slug}/"


def validate_recipe(recipe: Any, canonical_path: str, variation: int) -> dict[str, Any]:
    if not isinstance(recipe, dict):
        raise RuntimeError("recipe.make_recipe() must return a JSON object")
    required = {
        "version",
        "canonical_path",
        "variation",
        "seed",
        "family",
        "accents",
        "parameters",
    }
    missing = required.difference(recipe)
    if missing:
        raise RuntimeError(
            f"recipe is missing required fields: {', '.join(sorted(missing))}"
        )
    if recipe["version"] != "1":
        raise RuntimeError(f"unsupported recipe version: {recipe['version']!r}")
    if recipe["canonical_path"] != canonical_path:
        raise RuntimeError("recipe canonical_path does not match the requested post")
    if type(recipe["variation"]) is not int or recipe["variation"] != variation:
        raise RuntimeError("recipe variation does not match the requested candidate")
    if (
        not isinstance(recipe["seed"], str)
        or HEX_SEED_PATTERN.fullmatch(recipe["seed"]) is None
    ):
        raise RuntimeError("recipe seed must be a hexadecimal string")
    if recipe["family"] not in FAMILIES:
        raise RuntimeError(f"recipe family is not supported: {recipe['family']!r}")
    accents = recipe["accents"]
    if (
        not isinstance(accents, list)
        or not 2 <= len(accents) <= 4
        or not all(isinstance(item, str) for item in accents)
    ):
        raise RuntimeError("recipe accents must be a list of 2 to 4 strings")
    if "assigned_family" in recipe and recipe["assigned_family"] != recipe["family"]:
        raise RuntimeError("recipe assigned_family must match its family")
    if not isinstance(recipe["parameters"], dict):
        raise RuntimeError("recipe parameters must be a JSON object")
    try:
        json.dumps(recipe, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"recipe is not JSON serializable: {exc}") from exc
    return recipe


def _assert_no_symlink_components(workspace: Path, output_dir: Path) -> None:
    if not _is_relative_to(output_dir, workspace):
        raise UserInputError(f"job output resolves outside the workspace: {output_dir}")
    current = workspace
    for part in output_dir.relative_to(workspace).parts:
        current = current / part
        if current.is_symlink():
            raise UserInputError(
                f"job output path contains a symlink; choose a clean workspace path: {current}"
            )


def make_plan(
    slug: str,
    *,
    quality: str = "preview",
    variation: int = 0,
    workspace: str | Path | None = None,
    project_root: Path = PROJECT_ROOT,
    assigned_family: str | None = None,
    background: str = "theme",
) -> JobPlan:
    if quality not in ("preview", "final"):
        raise UserInputError("quality must be 'preview' or 'final'")
    if background not in BACKGROUND_MODES:
        raise UserInputError("background must be 'theme' or 'transparent'")
    if type(variation) is not int or variation < 0:
        raise UserInputError("variation must be a nonnegative integer")

    root = project_root.resolve()
    post_path, canonical_path = resolve_post(slug, root)
    del (
        post_path
    )  # The file is deliberately checked but never read for seed or recipe inputs.
    try:
        recipe_data = make_recipe(
            canonical_path, variation, assigned_family=assigned_family
        )
    except ValueError as exc:
        raise UserInputError(f"cannot create recipe for this variation: {exc}") from exc
    recipe = validate_recipe(recipe_data, canonical_path, variation)
    workspace_path = resolve_workspace(workspace, root)

    version = recipe["version"]
    if (
        not isinstance(version, str)
        or RECIPE_VERSION_PATTERN.fullmatch(version) is None
        or version in (".", "..")
    ):
        raise RuntimeError(
            f"recipe version is not safe for an output path: {version!r}"
        )
    output_candidate = workspace_path / slug / f"recipe-v{version}"
    if assigned_family is not None:
        output_candidate /= f"family-{recipe['family']}"
    if background == "transparent":
        output_candidate /= "background-transparent"
    output_candidate /= f"variation-{variation}"
    output_candidate /= quality
    _assert_no_symlink_components(workspace_path, output_candidate)
    output_dir = output_candidate.resolve()
    _assert_no_symlink_components(workspace_path, output_dir)
    if _is_relative_to(output_dir, root) or _is_relative_to(root, output_dir):
        raise UserInputError(
            f"job output must be separate from the blog repository: {output_dir}"
        )

    return JobPlan(
        slug=slug,
        canonical_path=canonical_path,
        variation=variation,
        quality=quality,
        recipe=recipe,
        workspace=workspace_path,
        output_dir=output_dir,
        scene_path=(root / "tools" / "signatures" / "scene.py").resolve(),
        project_root=root,
        background=background,
    )


def _candidate_executable(value: str) -> str | None:
    expanded = str(Path(value).expanduser())
    candidate = Path(expanded)
    if candidate.is_file():
        return str(candidate.resolve())
    found = shutil.which(expanded)
    if found:
        return str(Path(found).resolve())
    return None


def _windows_blender_candidates() -> list[Path]:
    roots: list[Path] = []
    for key in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(key)
        if value:
            path = Path(value)
            if path not in roots:
                roots.append(path)
    if not roots:
        roots.append(Path(r"C:\Program Files"))
    candidates: list[Path] = []
    for root in roots:
        foundation = root / "Blender Foundation"
        candidates.extend(foundation.glob("Blender */blender.exe"))
    return sorted(
        candidates,
        key=lambda path: tuple(
            int(part) for part in re.findall(r"\d+", path.parent.name)
        ),
        reverse=True,
    )


def discover_blender(explicit: str | None = None) -> tuple[str, bool, str | None]:
    """Return the command to display/run, whether it resolves, and a dry-run note if not."""
    if explicit is not None:
        found = _candidate_executable(explicit)
        if found:
            return found, True, None
        return (
            str(Path(explicit).expanduser()),
            False,
            f"explicit Blender executable was not found: {explicit}",
        )

    configured = os.environ.get("BLENDER_EXE")
    if configured:
        found = _candidate_executable(configured)
        if found:
            return found, True, None

    found = shutil.which("blender")
    if found:
        return str(Path(found).resolve()), True, None

    if os.name == "nt":
        for candidate in _windows_blender_candidates():
            if candidate.is_file():
                return str(candidate.resolve()), True, None
    elif sys.platform == "darwin":
        for candidate in (
            Path("/Applications/Blender.app/Contents/MacOS/Blender"),
            Path.home()
            / "Applications"
            / "Blender.app"
            / "Contents"
            / "MacOS"
            / "Blender",
        ):
            if candidate.is_file():
                return str(candidate.resolve()), True, None

    note = (
        f"BLENDER_EXE was not found: {configured}"
        if configured
        else "no Blender executable found in BLENDER_EXE, PATH, or standard install locations"
    )
    return "blender", False, note


def make_blender_command(
    blender: str, plan: JobPlan, *, overwrite: bool = False
) -> list[str]:
    command = [
        blender,
        "--background",
        "--factory-startup",
        "--threads",
        str(THREADS),
        "--python-exit-code",
        "1",
        "--python",
        str(plan.scene_path),
        "--",
        "--job",
        str(plan.job_path),
    ]
    if overwrite:
        command.append("--overwrite")
    return command


def make_job_document(plan: JobPlan) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "recipe": plan.recipe,
        "quality": plan.quality,
        "output_dir": str(plan.output_dir),
        "workspace_root": str(plan.workspace),
        "background": plan.background,
        "threads": THREADS,
    }


def _existing_job_matches(plan: JobPlan) -> bool:
    if not plan.job_path.is_file() or plan.job_path.is_symlink():
        return False
    try:
        existing = json.loads(plan.job_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(existing, dict)
        and existing.get("schema_version") == 1
        and existing.get("recipe") == plan.recipe
        and existing.get("quality") == plan.quality
        and existing.get("background", "theme") == plan.background
        and existing.get("output_dir") == str(plan.output_dir)
        and existing.get("workspace_root", str(plan.workspace)) == str(plan.workspace)
    )


def check_existing_output(plan: JobPlan, overwrite: bool) -> None:
    current = plan.workspace
    for part in plan.output_dir.relative_to(plan.workspace).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise UserInputError(f"job output parent must not be a symlink: {current}")
        if current.exists() and not current.is_dir():
            raise UserInputError(
                f"job output parent exists but is not a directory: {current}"
            )
    if plan.output_dir.is_symlink():
        raise UserInputError(
            f"job output directory must not be a symlink: {plan.output_dir}"
        )
    if not plan.output_dir.exists():
        return
    if not plan.output_dir.is_dir():
        raise UserInputError(
            f"job output path exists but is not a directory: {plan.output_dir}"
        )
    if not overwrite:
        raise UserInputError(
            f"output already exists: {plan.output_dir} (use --overwrite to replace this generated job)"
        )
    try:
        contents = list(plan.output_dir.iterdir())
    except OSError as exc:
        raise UserInputError(
            f"cannot inspect existing output directory {plan.output_dir}: {exc}"
        ) from exc
    if contents and not _existing_job_matches(plan):
        raise UserInputError(
            f"refusing to overwrite an unrecognized output directory; its job.json must match this recipe and quality: {plan.output_dir}"
        )


def _check_generated_paths(plan: JobPlan) -> None:
    _assert_no_symlink_components(plan.workspace, plan.output_dir)
    for name in GENERATED_FILES:
        path = plan.output_dir / name
        if path.is_symlink():
            raise UserInputError(
                f"refusing to overwrite generated output symlink: {path}"
            )
        if path.exists() and not path.is_file():
            raise UserInputError(
                f"generated output path exists but is not a file: {path}"
            )


def _write_job(plan: JobPlan, overwrite: bool) -> None:
    mode = "w" if overwrite else "x"
    try:
        with plan.job_path.open(mode, encoding="utf-8", newline="\n") as job_file:
            json.dump(
                make_job_document(plan),
                job_file,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            job_file.write("\n")
    except FileExistsError as exc:
        raise UserInputError(
            f"job file appeared during setup; refusing to overwrite it: {plan.job_path}"
        ) from exc
    except OSError as exc:
        raise RenderError(f"could not write job file {plan.job_path}: {exc}") from exc


def _prepare_output_directory(plan: JobPlan, overwrite: bool) -> None:
    check_existing_output(plan, overwrite)
    if not plan.output_dir.exists():
        try:
            plan.workspace.mkdir(parents=True, exist_ok=True)
            plan.output_dir.parent.mkdir(parents=True, exist_ok=True)
            _assert_no_symlink_components(plan.workspace, plan.output_dir)
            plan.output_dir.mkdir()
        except FileExistsError as exc:
            raise UserInputError(
                f"output directory appeared during setup; refusing to overwrite it: {plan.output_dir}"
            ) from exc
        except OSError as exc:
            raise RenderError(
                f"could not create output directory {plan.output_dir}: {exc}"
            ) from exc
    _check_generated_paths(plan)


def check_blender_version(blender: str) -> str:
    try:
        result = subprocess.run(
            [blender, "--version"],
            capture_output=True,
            text=True,
            timeout=BLENDER_VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RenderError(
            f"could not check Blender version using {blender!r}: {exc}"
        ) from exc
    version_output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    match = re.search(r"\bBlender\s+(\d+\.\d+(?:\.\d+)?)\b", version_output)
    if result.returncode != 0:
        raise RenderError(
            f"Blender version check failed with exit code {result.returncode}: {version_output.strip() or '(no output)'}"
        )
    if match is None:
        raise RenderError(
            f"could not identify a Blender version from {blender!r}: {version_output.strip() or '(no output)'}"
        )
    return match.group(1)


def _write_log_header(log_file: Any, command: list[str], blender_version: str) -> None:
    log_file.write(f"Blender {blender_version}\n")
    log_file.write(f"Command: {shlex.join(command)}\n\n")
    log_file.flush()


def run_blender(
    plan: JobPlan,
    blender: str,
    blender_version: str,
    timeout: int,
    *,
    overwrite: bool = False,
) -> None:
    command = make_blender_command(blender, plan, overwrite=overwrite)
    try:
        with plan.log_path.open("w", encoding="utf-8", errors="replace") as log_file:
            _write_log_header(log_file, command, blender_version)
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(plan.project_root),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            except OSError as exc:
                raise RenderError(
                    f"could not start Blender ({blender!r}): {exc}; see {plan.log_path}"
                ) from exc
            try:
                return_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                process.kill()
                process.wait()
                raise RenderError(
                    f"Blender exceeded the {timeout}-second timeout; process stopped; see {plan.log_path}"
                ) from exc
    except OSError as exc:
        raise RenderError(
            f"could not write Blender log {plan.log_path}: {exc}"
        ) from exc

    if return_code != 0:
        raise RenderError(
            f"Blender exited with code {return_code}; see {plan.log_path} for captured output"
        )


def validate_render_outputs(plan: JobPlan) -> list[Path]:
    try:
        _assert_no_symlink_components(plan.workspace, plan.output_dir)
    except UserInputError as exc:
        raise RenderError(
            f"render output path is no longer safe: {exc}; see {plan.log_path}"
        ) from exc
    if not plan.output_dir.is_dir() or plan.output_dir.resolve() != plan.output_dir:
        raise RenderError(
            f"render output directory is missing or resolves elsewhere: {plan.output_dir}; see {plan.log_path}"
        )

    output_paths: list[Path] = []
    for name in QUALITY_OUTPUTS:
        path = plan.output_dir / name
        if path.is_symlink():
            raise RenderError(
                f"render output must not be a symlink: {path}; see {plan.log_path}"
            )
        try:
            resolved = path.resolve(strict=True)
            size = path.stat().st_size
        except OSError as exc:
            raise RenderError(
                f"expected output is missing or unreadable: {path}: {exc}; see {plan.log_path}"
            ) from exc
        if not _is_relative_to(resolved, plan.output_dir) or _is_relative_to(
            resolved, plan.project_root
        ):
            raise RenderError(
                f"render output resolves outside its isolated output directory: {path} -> {resolved}"
            )
        if not resolved.is_file() or size == 0:
            raise RenderError(
                f"expected output is not a nonempty file: {path}; see {plan.log_path}"
            )
        output_paths.append(path)

    try:
        manifest = json.loads(plan.manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RenderError(
            f"could not read generated manifest {plan.manifest_path}: {exc}; see {plan.log_path}"
        ) from exc
    if not isinstance(manifest, dict):
        raise RenderError(
            f"generated manifest must be a JSON object: {plan.manifest_path}"
        )
    if manifest.get("schema_version") != 1:
        raise RenderError(
            f"generated manifest schema_version must be 1: {plan.manifest_path}"
        )
    if manifest.get("recipe") != plan.recipe or manifest.get("quality") != plan.quality:
        raise RenderError(
            f"generated manifest recipe/quality identity does not match this job: {plan.manifest_path}; see {plan.log_path}"
        )
    if manifest.get("background", "theme") != plan.background:
        raise RenderError(
            f"generated manifest background mode does not match this job: {plan.manifest_path}; see {plan.log_path}"
        )
    render_settings = manifest.get("render_settings")
    expected_render_settings = {
        "file_format": "PNG",
        "color_mode": "RGBA" if plan.background == "transparent" else "RGB",
        "film_transparent": True,
        "compositing": plan.background == "theme",
    }
    if not isinstance(render_settings, dict) or any(
        render_settings.get(key) != value
        for key, value in expected_render_settings.items()
    ):
        raise RenderError(
            f"generated manifest render settings do not match background mode {plan.background!r}: "
            f"{plan.manifest_path}; see {plan.log_path}"
        )
    themes = manifest.get("themes")
    expected_theme_outputs = {
        "latte": {"png": "latte.png", "blend": "latte.blend"},
        "mocha": {"png": "mocha.png", "blend": "mocha.blend"},
    }
    if not isinstance(themes, dict):
        raise RenderError(
            f"generated manifest is missing theme output paths: {plan.manifest_path}"
        )
    for theme, expected_outputs in expected_theme_outputs.items():
        actual_outputs = themes.get(theme)
        if not isinstance(actual_outputs, dict):
            raise RenderError(
                f"generated manifest is missing {theme} output paths: {plan.manifest_path}"
            )
        for kind, expected_name in expected_outputs.items():
            if actual_outputs.get(kind) != expected_name:
                raise RenderError(
                    f"generated manifest {theme}.{kind} must name {expected_name!r}: {plan.manifest_path}"
                )
    return output_paths


def print_dry_run(
    plan: JobPlan,
    blender: str,
    resolved: bool,
    note: str | None,
    family_choice: FamilyChoice,
    *,
    overwrite: bool = False,
) -> None:
    command = make_blender_command(blender, plan, overwrite=overwrite)
    identity = {
        "post_slug": plan.slug,
        "canonical_path": plan.canonical_path,
        "variation": plan.variation,
        "quality": plan.quality,
        "background": plan.background,
        "family_assignment": family_choice.status,
        "family": family_choice.family,
        "family_counts_before_choice": family_choice.counts,
        "recipe": plan.recipe,
        "workspace": str(plan.workspace),
        "registry_file": str(registry_path(plan.workspace)),
        "output_dir": str(plan.output_dir),
        "job_file": str(plan.job_path),
        "log_file": str(plan.log_path),
        "expected_outputs": [str(plan.output_dir / name) for name in QUALITY_OUTPUTS],
    }
    print("Signature study plan (no files written):")
    print(json.dumps(identity, ensure_ascii=False, sort_keys=True, indent=2))
    if resolved:
        print(f"Blender: {blender}")
    else:
        print(
            f"Blender unresolved: {note or 'not installed'} (dry-run does not require Blender)"
        )
    print("Command:")
    print(shlex.join(command))


def _ensure_workspace_directory(workspace: Path, project_root: Path) -> None:
    try:
        workspace.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RenderError(
            f"could not create study workspace {workspace}: {exc}"
        ) from exc
    resolved = workspace.resolve()
    if resolved != workspace:
        raise UserInputError(
            f"workspace changed through symlink resolution during setup: {workspace} -> {resolved}"
        )
    _assert_workspace_isolated(resolved, project_root)


def _make_requested_plan(
    slug: str,
    canonical_path: str,
    workspace: Path,
    family_choice: FamilyChoice,
    *,
    quality: str,
    variation: int,
    project_root: Path,
    background: str,
) -> JobPlan:
    plan = make_plan(
        slug,
        quality=quality,
        variation=variation,
        workspace=workspace,
        project_root=project_root,
        assigned_family=family_choice.family,
        background=background,
    )
    if plan.canonical_path != canonical_path:
        raise RuntimeError("post identity changed while preparing the signature job")
    return plan


def execute_plan(
    plan: JobPlan,
    blender: str,
    *,
    overwrite: bool,
    timeout: int,
    blender_version: str | None = None,
) -> list[Path]:
    if not plan.scene_path.is_file():
        raise RenderError(f"Blender scene runner is missing: {plan.scene_path}")
    checked_version = blender_version or check_blender_version(blender)
    _prepare_output_directory(plan, overwrite)
    _write_job(plan, overwrite)
    print(
        f"Rendering {plan.canonical_path} variation {plan.variation} "
        f"(family {plan.recipe['family']}, {plan.quality}) with Blender {checked_version}..."
    )
    run_blender(plan, blender, checked_version, timeout, overwrite=overwrite)
    return validate_render_outputs(plan)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _, canonical_path = resolve_post(args.slug, PROJECT_ROOT)
        workspace = resolve_workspace(args.workspace, PROJECT_ROOT)
        blender, resolved, note = discover_blender(args.blender)
        if args.dry_run:
            registry = load_registry(workspace)
            choice = choose_family(canonical_path, registry.assignments)
            plan = _make_requested_plan(
                args.slug,
                canonical_path,
                workspace,
                choice,
                quality=args.quality,
                variation=args.variation,
                project_root=PROJECT_ROOT,
                background=args.background,
            )
            check_existing_output(plan, args.overwrite)
            print_dry_run(
                plan, blender, resolved, note, choice, overwrite=args.overwrite
            )
            return 0
        if not resolved:
            raise RenderError(
                f"{note or 'Blender was not found'}; install Blender or pass --blender PATH"
            )
        scene_path = (PROJECT_ROOT / "tools" / "signatures" / "scene.py").resolve()
        if not scene_path.is_file():
            raise RenderError(f"Blender scene runner is missing: {scene_path}")
        blender_version = check_blender_version(blender)
        _ensure_workspace_directory(workspace, PROJECT_ROOT)

        prepared: dict[str, JobPlan] = {}

        def output_preflight(choice: FamilyChoice) -> None:
            plan = _make_requested_plan(
                args.slug,
                canonical_path,
                workspace,
                choice,
                quality=args.quality,
                variation=args.variation,
                project_root=PROJECT_ROOT,
                background=args.background,
            )
            check_existing_output(plan, args.overwrite)
            prepared["plan"] = plan

        choice = assign_family(workspace, canonical_path, before_save=output_preflight)
        plan = prepared["plan"]
        if choice.status == "proposed":
            print(
                f"Registered family {choice.family} for {canonical_path} in {registry_path(workspace)}"
            )
        else:
            print(f"Using registered family {choice.family} for {canonical_path}")
        files = execute_plan(
            plan,
            blender,
            overwrite=args.overwrite,
            timeout=args.timeout,
            blender_version=blender_version,
        )
    except UserInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except RegistryError as exc:
        print(f"error: signature registry: {exc}", file=sys.stderr)
        return 1
    except RenderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: filesystem or process operation failed: {exc}", file=sys.stderr)
        return 1

    print("Render complete:")
    for path in files:
        print(f"  {path}")
    print(f"  {plan.job_path}")
    print(f"  {plan.log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
