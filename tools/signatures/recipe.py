"""Pure, deterministic per-post signature recipes (no Blender dependency)."""

from __future__ import annotations

import hashlib
import math
import re
from urllib.parse import urlsplit

RECIPE_VERSION = "1"
MAX_VARIATION = 9999
FAMILIES = ("ribbon-v1", "open-crescent", "open-hairpin")
ACCENTS = (
    "rosewater",
    "flamingo",
    "pink",
    "mauve",
    "red",
    "maroon",
    "peach",
    "yellow",
    "green",
    "teal",
    "sky",
    "sapphire",
    "blue",
    "lavender",
)

_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")

# Each anchor has three restrained companions. Every supported Catppuccin accent
# can anchor a colorway, while a recipe uses only two to four colors total.
_HARMONIES = {
    "rosewater": ("blue", "teal", "lavender"),
    "flamingo": ("teal", "sapphire", "blue"),
    "pink": ("teal", "lavender", "peach"),
    "mauve": ("peach", "sapphire", "teal"),
    "red": ("green", "blue", "lavender"),
    "maroon": ("sky", "teal", "peach"),
    "peach": ("blue", "lavender", "mauve"),
    "yellow": ("blue", "mauve", "teal"),
    "green": ("mauve", "pink", "rosewater"),
    "teal": ("peach", "lavender", "pink"),
    "sky": ("maroon", "peach", "blue"),
    "sapphire": ("rosewater", "peach", "mauve"),
    "blue": ("peach", "teal", "lavender"),
    "lavender": ("teal", "peach", "mauve"),
}


def make_recipe(
    canonical_path: str,
    variation: int = 0,
    *,
    assigned_family: str | None = None,
) -> dict:
    """Return the same JSON-safe geometry/color recipe for the same post/version.

    ``canonical_path`` may be a ``/posts/<slug>/`` path or an HTTP(S) URL whose
    path has that exact form. A missing final slash and query/fragment are
    normalized away; other routes and non-kebab slugs are rejected. When
    ``assigned_family`` is omitted, version-1 output remains unchanged.
    """
    path = _canonical_post_path(canonical_path)
    if type(variation) is not int or not 0 <= variation <= MAX_VARIATION:
        raise ValueError(f"variation must be an integer from 0 to {MAX_VARIATION}")
    if assigned_family is not None and assigned_family not in FAMILIES:
        raise ValueError(f"assigned_family must be one of {FAMILIES!r}")

    seeds = {
        domain: _domain_seed(domain, path, variation)
        for domain in ("family", "geometry", "strands", "palette")
    }
    root_seed = _domain_seed("recipe", path, variation)
    family_roll = _unit(seeds["family"])
    family = (
        assigned_family
        or FAMILIES[min(int(family_roll * len(FAMILIES)), len(FAMILIES) - 1)]
    )
    palette_rolls = _units(seeds["palette"], 2)
    anchor = ACCENTS[min(int(palette_rolls[0] * len(ACCENTS)), len(ACCENTS) - 1)]
    accent_count = 2 + min(int(palette_rolls[1] * 3), 2)
    accents = [anchor, *_HARMONIES[anchor][: accent_count - 1]]

    geometry_rolls = _units(seeds["geometry"], 12)
    global_parameters = {
        "scale_x": _between(geometry_rolls[0], 0.94, 1.06),
        "scale_z": _between(geometry_rolls[1], 0.94, 1.06),
        "shear": _between(geometry_rolls[2], -0.045, 0.045),
    }
    shape_parameters = _shape_parameters(family, geometry_rolls[3:])
    strand_rolls = _units(seeds["strands"], 3)
    strand_parameters = {
        "spread_scale": _between(strand_rolls[0], 0.92, 1.08),
        "wave_scale": _between(strand_rolls[1], 0.85, 1.15),
        "depth_scale": _between(strand_rolls[2], 0.85, 1.15),
    }

    recipe = {
        "version": RECIPE_VERSION,
        "canonical_path": path,
        "variation": variation,
        "seed": root_seed.hex(),
        "family": family,
        "accents": accents,
        "seeds": {name: value.hex() for name, value in seeds.items()},
        "parameters": {
            "global": global_parameters,
            "shape": shape_parameters,
            "strands": strand_parameters,
        },
    }
    if assigned_family is not None:
        recipe["assigned_family"] = assigned_family
    _assert_finite(recipe)
    return recipe


def _canonical_post_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("canonical_path must be a non-empty /posts/<slug>/ path")
    value = value.strip()
    if "\\" in value:
        raise ValueError("canonical_path must use URL path separators")

    if value.startswith("//"):
        raise ValueError("protocol-relative URLs are not valid canonical paths")
    if re.match(r"^[a-z][a-z\d+.-]*://", value, re.IGNORECASE):
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise ValueError("canonical_path URL must use http or https")
        path = parsed.path
    else:
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            raise ValueError("canonical_path must be a post path or an HTTP(S) URL")
        path = parsed.path

    path = path.removesuffix("/")
    match = re.fullmatch(r"/posts/([^/]+)", path)
    if match is None:
        raise ValueError("canonical_path must identify exactly /posts/<slug>/")
    slug = match.group(1)
    if _SLUG.fullmatch(slug) is None:
        raise ValueError("post slug must be lowercase kebab-case ASCII")
    return f"/posts/{slug}/"


def _domain_seed(domain: str, canonical_path: str, variation: int) -> bytes:
    payload = f"signature-recipe-v{RECIPE_VERSION}\0{domain}\0{canonical_path}\0{variation}".encode()
    return hashlib.sha256(payload).digest()


def _unit(seed: bytes, counter: int = 0) -> float:
    digest = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
    return (int.from_bytes(digest[:8], "big") >> 11) / (1 << 53)


def _units(seed: bytes, count: int) -> list[float]:
    return [_unit(seed, counter) for counter in range(count)]


def _between(value: float, minimum: float, maximum: float) -> float:
    return round(minimum + value * (maximum - minimum), 6)


def _shape_parameters(family: str, values: list[float]) -> dict[str, float]:
    if family == "ribbon-v1":
        return {
            "loop_opening": _between(values[0], 0.88, 1.12),
            "loop_lift": _between(values[1], -0.32, 0.32),
            "return_sweep": _between(values[2], -0.35, 0.35),
            "depth_weave": _between(values[3], -0.18, 0.18),
        }
    if family == "open-crescent":
        return {
            "bow_scale": _between(values[0], 0.88, 1.12),
            "horn_asymmetry": _between(values[1], -0.42, 0.42),
            "sweep_scale": _between(values[2], 0.90, 1.10),
            "counterflow_length": _between(values[3], 0.86, 1.14),
        }
    if family == "open-hairpin":
        return {
            "crown_span": _between(values[0], 0.88, 1.12),
            "crown_lift": _between(values[1], -0.34, 0.34),
            "entry_sweep": _between(values[2], -0.32, 0.32),
            "return_lag": _between(values[3], -0.34, 0.34),
        }
    raise ValueError(f"unsupported signature family: {family}")


def _assert_finite(value: object, path: str = "recipe") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} contains a non-finite number")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")


__all__ = ["ACCENTS", "FAMILIES", "MAX_VARIATION", "RECIPE_VERSION", "make_recipe"]
