"""Blender worker for deterministic paired ribbon signature renders.

The script is run by Blender's bundled Python. Its only import from this
folder is the standard-library-only recipe module; it never integrates with
the website build and refuses output paths inside or above the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Prevent Blender's bundled Python from leaving bytecode in the repository.
sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bpy  # type: ignore[import-not-found]  # Blender runtime only
from mathutils import Vector  # type: ignore[import-not-found]  # Blender runtime only
from recipe import FAMILIES, make_recipe

SCHEMA_VERSION = 1
BACKGROUND_MODES = ("theme", "transparent")
OUTPUT_NAMES = (
    "latte.png",
    "mocha.png",
    "latte.blend",
    "mocha.blend",
    "manifest.json",
)
REPO_ROOT = SCRIPT_DIR.parents[1].resolve()
CAMERA_ORTHO_SCALE = 9.75
CAMERA_MARGIN = 0.93
FINAL_SIZE = (1600, 1520)
PREVIEW_SIZE = (800, 760)
THREAD_CAP = 4

# Original control paths adapted from the approved Study 06/07/08 masters.
# Coordinates are world-space X/Y/Z; the camera looks along +Y.
PATHS = {
    "ribbon-v1": {
        "crest": [
            (-4.08, -0.18, -1.55),
            (-3.78, -0.28, -0.28),
            (-3.08, -0.44, 1.22),
            (-1.84, -0.15, 2.54),
            (-0.23, 0.15, 3.07),
            (1.48, 0.28, 2.88),
            (2.94, 0.04, 2.03),
            (3.80, -0.48, 0.66),
            (3.28, -0.78, -0.26),
            (2.02, -0.47, -0.78),
            (0.78, 0.03, -1.45),
            (0.08, -0.36, -2.55),
            (0.62, -0.56, -3.15),
            (2.11, -0.18, -3.01),
            (3.03, 0.24, -2.18),
        ],
        "inner": [
            (-3.49, 0.67, -1.80),
            (-2.77, 0.77, -0.63),
            (-1.74, 0.87, 0.31),
            (-0.39, 0.72, 0.75),
            (0.91, 0.35, 0.19),
            (1.78, 0.76, -0.76),
            (1.48, 0.70, -1.73),
            (0.25, 0.40, -2.34),
            (-1.28, 0.55, -2.12),
            (-2.31, 0.61, -1.13),
        ],
        "drift": [
            (-3.42, 0.87, -2.08),
            (-2.18, 0.99, -2.74),
            (-0.61, 0.90, -3.05),
            (1.04, 0.72, -2.72),
            (2.43, 0.55, -1.95),
            (3.49, 0.36, -0.76),
            (3.78, 0.19, 0.38),
            (3.21, 0.10, 1.31),
        ],
    },
    "open-crescent": {
        "crest": [
            (-4.02, -0.18, 0.72),
            (-3.92, -0.25, -0.08),
            (-3.48, -0.34, -1.02),
            (-2.60, -0.26, -1.96),
            (-1.28, 0.02, -2.63),
            (0.18, 0.24, -2.92),
            (1.64, 0.16, -2.60),
            (2.92, -0.12, -1.72),
            (3.70, -0.36, -0.38),
            (3.98, -0.42, 0.72),
            (3.70, -0.30, 1.48),
        ],
        "inner": [
            (-3.30, 0.56, 0.04),
            (-3.18, 0.50, -0.62),
            (-2.62, 0.34, -1.38),
            (-1.52, 0.18, -1.98),
            (-0.16, 0.02, -2.22),
            (1.20, 0.18, -1.98),
            (2.34, 0.39, -1.28),
            (3.05, 0.56, -0.32),
            (3.12, 0.62, 0.80),
        ],
        "drift": [
            (2.82, 0.76, -0.58),
            (2.22, 0.62, -1.47),
            (1.18, 0.42, -2.13),
            (-0.05, 0.26, -2.42),
            (-1.26, 0.31, -2.23),
            (-2.24, 0.52, -1.76),
            (-2.82, 0.70, -1.13),
        ],
    },
    "open-hairpin": {
        "crest": [
            (-2.86, -0.18, -3.58),
            (-2.88, -0.24, -2.70),
            (-2.82, -0.34, -1.42),
            (-2.65, -0.28, 0.03),
            (-2.25, -0.16, 1.48),
            (-1.50, 0.05, 2.72),
            (-0.42, 0.28, 3.48),
            (0.86, 0.16, 3.64),
            (1.88, -0.12, 3.20),
            (2.52, -0.35, 2.18),
            (2.71, -0.48, 0.84),
            (2.54, -0.34, -0.38),
            (2.12, -0.10, -1.48),
            (1.54, 0.10, -2.45),
            (1.62, 0.24, -3.18),
        ],
        "inner": [
            (-2.35, 0.67, -2.82),
            (-2.33, 0.70, -1.55),
            (-2.15, 0.72, -0.18),
            (-1.77, 0.67, 1.14),
            (-1.08, 0.58, 2.23),
            (-0.12, 0.48, 2.83),
            (0.92, 0.46, 2.88),
            (1.69, 0.50, 2.25),
            (2.02, 0.54, 1.25),
            (1.94, 0.57, 0.21),
            (1.55, 0.54, -0.85),
            (1.08, 0.48, -1.86),
            (0.96, 0.42, -2.82),
        ],
        "drift": [
            (1.86, 0.94, -3.05),
            (1.78, 0.88, -2.32),
            (1.78, 0.80, -1.48),
            (2.05, 0.70, -0.47),
            (2.27, 0.60, 0.61),
            (2.20, 0.48, 1.63),
            (1.73, 0.36, 2.48),
            (0.92, 0.30, 3.00),
            (-0.10, 0.29, 3.12),
            (-1.17, 0.27, 2.77),
            (-1.97, 0.22, 2.00),
            (-2.35, 0.16, 1.02),
            (-2.43, 0.12, 0.42),
        ],
    },
}

RIBBON_SPECS = {
    "crest": {
        "count": 24,
        "cluster_counts": (7, 11, 6),
        "cluster_ranges": ((-0.47, -0.30), (-0.15, 0.12), (0.30, 0.48)),
        "spread": 0.94,
        "width": 0.42 * 1.12,
        "phase": 0.10,
        "roll": 0.42,
        "cycles": 1.45,
    },
    "inner": {
        "count": 16,
        "cluster_counts": (5, 7, 4),
        "cluster_ranges": ((-0.45, -0.26), (-0.06, 0.13), (0.29, 0.46)),
        "spread": 0.69,
        "width": 0.29 * 1.12,
        "phase": 0.63,
        "roll": 0.56,
        "cycles": 1.8,
    },
    "drift": {
        "count": 12,
        "cluster_counts": (4, 5, 3),
        "cluster_ranges": ((-0.43, -0.27), (-0.08, 0.12), (0.30, 0.45)),
        "spread": 0.50,
        "width": 0.19 * 1.12,
        "phase": 0.22,
        "roll": 0.36,
        "cycles": 1.1,
    },
}

CATPPUCCIN = {
    "mocha": {
        "base": "#1e1e2e",
        "mantle": "#181825",
        "text": "#cdd6f4",
        "accents": {
            "rosewater": "#f5e0dc",
            "flamingo": "#f2cdcd",
            "pink": "#f5c2e7",
            "mauve": "#cba6f7",
            "red": "#f38ba8",
            "maroon": "#eba0ac",
            "peach": "#fab387",
            "yellow": "#f9e2af",
            "green": "#a6e3a1",
            "teal": "#94e2d5",
            "sky": "#89dceb",
            "sapphire": "#74c7ec",
            "blue": "#89b4fa",
            "lavender": "#b4befe",
        },
        "body": {
            "roughness": 0.58,
            "transmission": 0.58,
            "alpha": 0.31,
            "emission": 0.025,
        },
        "fiber_emission": {
            "soft_text": 0.105,
            "soft_secondary": 0.105,
            "soft_blue": 0.11,
            "soft_mauve": 0.105,
            "high_text": 0.22,
            "high_secondary": 0.20,
            "accent_mauve": 0.24,
            "accent_cool": 0.27,
            "accent_blue": 0.24,
            "accent_warm": 0.22,
        },
        "light_roles": ("text", "sapphire", "lavender"),
    },
    "latte": {
        "base": "#eff1f5",
        "mantle": "#e6e9ef",
        "text": "#4c4f69",
        "accents": {
            "rosewater": "#dc8a78",
            "flamingo": "#dd7878",
            "pink": "#ea76cb",
            "mauve": "#8839ef",
            "red": "#d20f39",
            "maroon": "#e64553",
            "peach": "#fe640b",
            "yellow": "#df8e1d",
            "green": "#40a02b",
            "teal": "#179299",
            "sky": "#04a5e5",
            "sapphire": "#209fb5",
            "blue": "#1e66f5",
            "lavender": "#7287fd",
        },
        "body": {
            "roughness": 0.54,
            "transmission": 0.72,
            "alpha": 0.26,
            "emission": 0.018,
        },
        "fiber_emission": {
            "soft_text": 0.10,
            "soft_secondary": 0.075,
            "soft_blue": 0.075,
            "soft_mauve": 0.075,
            "high_text": 0.18,
            "high_secondary": 0.16,
            "accent_mauve": 0.18,
            "accent_cool": 0.18,
            "accent_blue": 0.18,
            "accent_warm": 0.15,
        },
        "light_roles": ("base", "base", "base"),
    },
}

FIBER_MATERIAL_KEYS = (
    "soft_text",
    "soft_0",
    "soft_1",
    "soft_2",
    "high_text",
    "high_0",
    "accent_0",
    "accent_1",
    "accent_2",
    "accent_3",
)


def hex_to_linear(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.lstrip("#")
    srgb = [int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4)]
    return tuple(
        component / 12.92
        if component <= 0.04045
        else ((component + 0.055) / 1.055) ** 2.4
        for component in srgb
    )


def rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    return (*hex_to_linear(hex_color), alpha)


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _bell(value: float, center: float, width: float) -> float:
    return math.exp(-(((value - center) / width) ** 2))


def _catmull_rom(
    points: list[tuple[float, float, float]], steps: int = 11
) -> list[tuple[float, float, float]]:
    sampled = []
    for index in range(len(points) - 1):
        p0 = points[max(0, index - 1)]
        p1 = points[index]
        p2 = points[index + 1]
        p3 = points[min(len(points) - 1, index + 2)]
        for step in range(steps):
            t = step / steps
            t2, t3 = t * t, t * t * t
            sampled.append(
                tuple(
                    0.5
                    * (
                        2.0 * p1[axis]
                        + (-p0[axis] + p2[axis]) * t
                        + (2.0 * p0[axis] - 5.0 * p1[axis] + 4.0 * p2[axis] - p3[axis])
                        * t2
                        + (-p0[axis] + 3.0 * p1[axis] - 3.0 * p2[axis] + p3[axis]) * t3
                    )
                    for axis in range(3)
                )
            )
    sampled.append(points[-1])
    return sampled


def _transform_paths(
    recipe: dict[str, Any],
) -> tuple[dict[str, list[tuple[float, float, float]]], float]:
    family = recipe["family"]
    parameters = recipe["parameters"]
    shape = parameters["shape"]
    global_parameters = parameters["global"]
    transformed: dict[str, list[tuple[float, float, float]]] = {}

    for ribbon_name, control_points in PATHS[family].items():
        points = [Vector(point) for point in control_points]
        count = len(points)
        for index, point in enumerate(points):
            t = index / (count - 1)
            if family == "ribbon-v1":
                central = _bell(t, 0.51, 0.31)
                if ribbon_name == "crest":
                    point.x *= 1.0 + (shape["loop_opening"] - 1.0) * central
                    point.z += shape["loop_lift"] * _bell(t, 0.34, 0.25)
                    point.x += shape["return_sweep"] * _bell(t, 0.82, 0.23)
                    point.y += shape["depth_weave"] * _bell(t, 0.55, 0.19)
                elif ribbon_name == "inner":
                    point.x *= 1.0 + (shape["loop_opening"] - 1.0) * central * 0.68
                    point.z -= shape["loop_lift"] * _bell(t, 0.56, 0.29) * 0.50
                    point.y -= shape["depth_weave"] * _bell(t, 0.48, 0.20) * 0.65
                else:
                    point.x += shape["return_sweep"] * (t - 0.5) * 1.5
                    point.z += shape["loop_lift"] * _bell(t, 0.38, 0.29) * 0.35
            elif family == "open-crescent":
                if ribbon_name == "crest":
                    point.x *= shape["sweep_scale"]
                    point.z -= 2.5 * (shape["bow_scale"] - 1.0) * _bell(t, 0.52, 0.34)
                    point.z += shape["horn_asymmetry"] * (2.0 * t - 1.0) * 0.58
                elif ribbon_name == "inner":
                    point.z -= 1.45 * (shape["bow_scale"] - 1.0) * _bell(t, 0.50, 0.38)
                    point.z += shape["horn_asymmetry"] * (2.0 * t - 1.0) * 0.32
                else:
                    point.x *= shape["counterflow_length"]
                    point.z -= 0.72 * (shape["bow_scale"] - 1.0) * _bell(t, 0.48, 0.37)
                    point.x += shape["horn_asymmetry"] * _bell(t, 0.72, 0.24) * 0.24
            else:
                crown = _bell(t, 0.50, 0.31)
                if ribbon_name == "crest":
                    point.x *= 1.0 + (shape["crown_span"] - 1.0) * crown
                    point.z += shape["crown_lift"] * crown
                    point.x += shape["entry_sweep"] * _bell(t, 0.16, 0.21)
                    point.z += shape["return_lag"] * _bell(t, 0.91, 0.19)
                elif ribbon_name == "inner":
                    point.x *= 1.0 + (shape["crown_span"] - 1.0) * crown * 0.62
                    point.z += shape["crown_lift"] * _bell(t, 0.53, 0.30) * 0.60
                    point.x += shape["return_lag"] * _bell(t, 0.89, 0.20) * 0.45
                else:
                    point.z += shape["crown_lift"] * _bell(t, 0.47, 0.34) * 0.32
                    point.x += shape["entry_sweep"] * _bell(t, 0.15, 0.22) * 0.55
                    point.x += shape["return_lag"] * _bell(t, 0.86, 0.21) * 0.30

            point.x = (
                point.x * global_parameters["scale_x"]
                + point.z * global_parameters["shear"]
            )
            point.z *= global_parameters["scale_z"]
        transformed[ribbon_name] = _catmull_rom(
            [tuple(point) for point in points], steps=11
        )

    return transformed, 1.0


def _strand_frames(
    samples: list[tuple[float, float, float]],
    roll_phase: float,
    roll_amount: float,
    roll_cycles: float,
) -> list[tuple[Vector, Vector, float]]:
    result = []
    for index, sample in enumerate(samples):
        t = index / (len(samples) - 1)
        before = Vector(samples[max(0, index - 1)])
        after = Vector(samples[min(len(samples) - 1, index + 1)])
        tangent = after - before
        tangent = (
            tangent.normalized() if tangent.length > 1e-8 else Vector((1.0, 0.0, 0.0))
        )
        screen_side = Vector((-(after.z - before.z), 0.0, after.x - before.x))
        if screen_side.length < 1e-8:
            screen_side = Vector((1.0, 0.0, 0.0))
        screen_side.normalize()
        depth_side = tangent.cross(screen_side)
        if depth_side.length < 1e-8:
            depth_side = Vector((0.0, -1.0, 0.0))
        depth_side.normalize()
        angle = roll_phase + roll_amount * math.sin(
            math.tau * roll_cycles * t + roll_phase
        )
        side = (
            screen_side * math.cos(angle) + depth_side * math.sin(angle)
        ).normalized()
        result.append((Vector(sample), side, t))
    return result


def _make_mesh_material(name: str) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = (0.7, 0.7, 0.7, 0.35)
    material.use_nodes = True
    shader = next(
        node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"
    )
    shader.inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1.0)
    shader.inputs["Roughness"].default_value = 0.58
    shader.inputs["Alpha"].default_value = 0.31
    shader.inputs["Thin Wall"].default_value = True
    shader.inputs["Transmission Weight"].default_value = 0.58
    shader.inputs["Emission Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    shader.inputs["Emission Strength"].default_value = 0.025
    shader.inputs["IOR"].default_value = 1.34
    shader.inputs["Coat Weight"].default_value = 0.045
    shader.inputs["Coat Roughness"].default_value = 0.52

    color_node = material.node_tree.nodes.new("ShaderNodeVertexColor")
    color_node.layer_name = "RibbonTint"
    material.node_tree.links.new(
        color_node.outputs["Color"], shader.inputs["Base Color"]
    )
    material.node_tree.links.new(
        color_node.outputs["Color"], shader.inputs["Emission Color"]
    )
    return material


def _make_fiber_material(name: str) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    shader = next(
        node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"
    )
    shader.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    shader.inputs["Roughness"].default_value = 0.56
    shader.inputs["Metallic"].default_value = 0.0
    shader.inputs["Coat Weight"].default_value = 0.025
    shader.inputs["Emission Color"].default_value = (0.8, 0.8, 0.8, 1.0)
    shader.inputs["Emission Strength"].default_value = 0.1
    return material


def _material_shader(
    material: bpy.types.Material,
) -> bpy.types.ShaderNodeBsdfPrincipled:
    return next(
        node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"
    )


def _make_ribbon_mesh(
    name: str,
    frames: list[tuple[Vector, Vector, float]],
    width: float,
    y_bias: float,
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    ribbon_name: str,
) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for index, (center, side, t) in enumerate(frames):
        taper = min(_smoothstep(t / 0.075), _smoothstep((1.0 - t) / 0.075))
        swell = 0.76 + 0.24 * math.sin(math.pi * t) ** 2
        half = width * (0.015 + 0.985 * taper) * swell * 0.5
        left = center + side * half
        right = center - side * half
        left.y += y_bias
        right.y += y_bias
        vertices.extend((tuple(left), tuple(right)))
        if index < len(frames) - 1:
            first = index * 2
            faces.append((first, first + 1, first + 3, first + 2))

    mesh = bpy.data.meshes.new(f"{name} | softly tinted support")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    color_attribute = mesh.color_attributes.new(
        name="RibbonTint", type="FLOAT_COLOR", domain="POINT"
    )
    for item in color_attribute.data:
        item.color = (0.5, 0.5, 0.5, 1.0)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.data.materials.append(material)
    obj["signature_family"] = ribbon_name
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return obj


def _fiber_points(
    frames: list[tuple[Vector, Vector, float]],
    position: float,
    spread: float,
    depth_offset: float,
    phase: float,
    wave_amount: float,
    depth_phase: float,
) -> list[tuple[float, float, float]]:
    result = []
    for center, side, t in frames:
        gather = 0.79 + 0.21 * math.sin(math.pi * t) ** 1.3
        wave = wave_amount * math.sin(math.tau * 1.5 * t + phase)
        wave += wave_amount * 0.38 * math.sin(math.tau * 4.2 * t - phase * 0.63)
        point = center + side * (position * spread * gather + wave)
        point.y += depth_offset + 0.045 * math.sin(math.tau * 1.7 * t + depth_phase)
        result.append(tuple(point))
    return result


def _tapered_radii(count: int, fade: float = 0.065) -> list[float]:
    return [
        min(
            _smoothstep((index / (count - 1)) / fade),
            _smoothstep((1.0 - index / (count - 1)) / fade),
        )
        for index in range(count)
    ]


def _make_curve_object(
    name: str,
    points: list[tuple[float, float, float]],
    radius: float,
    radii: list[float],
    material: bpy.types.Material,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    spline.points.foreach_set(
        "co", [value for point in points for value in (*point, 1.0)]
    )
    spline.points.foreach_set("radius", radii)
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def _rng_for_family(seed_hex: str, family_name: str) -> random.Random:
    digest = hashlib.sha256(f"{seed_hex}\0{family_name}".encode("ascii")).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))


def _clustered_offsets(
    counts: tuple[int, ...],
    ranges: tuple[tuple[float, float], ...],
    rng: random.Random,
) -> list[float]:
    offsets = [
        rng.uniform(low, high)
        for count, (low, high) in zip(counts, ranges, strict=True)
        for _ in range(count)
    ]
    rng.shuffle(offsets)
    return offsets


def _add_strand_clusters(
    collection: bpy.types.Collection,
    fiber_materials: dict[str, bpy.types.Material],
    frames_by_family: dict[str, list[tuple[Vector, Vector, float]]],
    strand_parameters: dict[str, float],
    strands_seed: str,
) -> tuple[int, int, int]:
    created = 0
    high_count = 0
    overlay_count = 0
    accent_maps = {
        "crest": {
            3: (0.57, 0.68, "accent_1"),
            18: (0.60, 0.70, "accent_2"),
            7: (0.19, 0.29, "accent_0"),
        },
        "inner": {5: (0.30, 0.41, "accent_1"), 12: (0.67, 0.77, "accent_0")},
        "drift": {6: (0.56, 0.67, "accent_3")},
    }
    for family_name, spec in RIBBON_SPECS.items():
        frames = frames_by_family[family_name]
        rng = _rng_for_family(strands_seed, family_name)
        offsets = _clustered_offsets(
            spec["cluster_counts"], spec["cluster_ranges"], rng
        )
        accent_map = accent_maps[family_name]
        spread = spec["spread"] * strand_parameters["spread_scale"]
        for index, position in enumerate(offsets):
            phase = rng.uniform(-math.pi, math.pi)
            depth_offset = rng.uniform(-0.16, 0.14) * strand_parameters["depth_scale"]
            wave_amount = rng.uniform(0.012, 0.038) * strand_parameters["wave_scale"]
            depth_phase = rng.uniform(-math.pi, math.pi)
            if index % 9 == 2:
                material_key = "high_text" if family_name == "crest" else "high_0"
                high_count += 1
            elif index % 7 == 3:
                material_key = "soft_2"
            elif index % 5 == 1:
                material_key = "soft_1"
            elif index % 4 == 0:
                material_key = "soft_0"
            else:
                material_key = "soft_text"

            accent = accent_map.get(index)
            start = 0.0 if rng.random() < 0.30 or accent else rng.uniform(0.015, 0.18)
            end = 1.0 if rng.random() < 0.30 or accent else rng.uniform(0.83, 0.99)
            if end - start < 0.62:
                start, end = max(0.0, end - 0.64), min(1.0, start + 0.64)
            all_points = _fiber_points(
                frames, position, spread, depth_offset, phase, wave_amount, depth_phase
            )
            chosen = [
                point_index
                for point_index, (_, _, t) in enumerate(frames)
                if start <= t <= end
            ]
            points = [all_points[point_index] for point_index in chosen]
            if len(points) < 2:
                continue
            radius = rng.uniform(0.0038, 0.0064)
            if material_key.startswith("high_"):
                radius *= 1.12
            _make_curve_object(
                f"{family_name} | flowing fibre {index + 1:02d}",
                points,
                radius,
                _tapered_radii(len(points)),
                fiber_materials[material_key],
                collection,
            )
            created += 1

            if accent is not None:
                accent_start, accent_end, accent_key = accent
                accent_indices = [
                    point_index
                    for point_index in chosen
                    if accent_start <= frames[point_index][2] <= accent_end
                ]
                fragment = [all_points[point_index] for point_index in accent_indices]
                if len(fragment) > 2:
                    _make_curve_object(
                        f"{family_name} | local refraction {index + 1:02d}",
                        fragment,
                        radius * 0.92,
                        _tapered_radii(len(fragment), fade=0.16),
                        fiber_materials[accent_key],
                        collection,
                    )
                    overlay_count += 1
    return created, high_count, overlay_count


def _color_lerp(
    a: tuple[float, float, float], b: tuple[float, float, float], t: float
) -> tuple[float, float, float]:
    return tuple(a[index] * (1.0 - t) + b[index] * t for index in range(3))


def _ribbon_color(
    family_name: str, t: float, palette: dict[str, Any]
) -> tuple[float, float, float]:
    accents = palette["accent_rgb"]
    roles = {
        "crest": (0, ((0.22, 0.12, 1), (0.63, 0.12, 2), (0.82, 0.08, 3))),
        "inner": (1, ((0.32, 0.13, 2), (0.69, 0.12, 3))),
        "drift": (min(2, len(accents) - 1), ((0.63, 0.12, 1),)),
    }
    base_index, stops = roles[family_name]
    color = accents[base_index % len(accents)]
    for center, width, accent_index in stops:
        fade = min(0.06, width * 0.3)
        weight = _smoothstep((t - (center - width * 0.5)) / fade) * (
            1.0 - _smoothstep((t - (center + width * 0.5)) / fade)
        )
        color = _color_lerp(color, accents[accent_index % len(accents)], weight * 0.82)
    return color


def _apply_body_colors(scene: bpy.types.Scene, palette: dict[str, Any]) -> None:
    for obj in scene.objects:
        if obj.type != "MESH" or "signature_family" not in obj:
            continue
        color_attribute = obj.data.color_attributes.get("RibbonTint")
        if color_attribute is None:
            raise RuntimeError(f"missing RibbonTint color data on {obj.name}")
        pair_count = len(color_attribute.data) // 2
        for vertex_index, item in enumerate(color_attribute.data):
            t = (vertex_index // 2) / max(1, pair_count - 1)
            color = _ribbon_color(obj["signature_family"], t, palette)
            item.color = (*color, 1.0)


def _set_principled_input(
    shader: bpy.types.ShaderNodeBsdfPrincipled, name: str, value: Any
) -> None:
    socket = shader.inputs.get(name)
    if socket is not None:
        socket.default_value = value


def _ensure_world(scene: bpy.types.Scene) -> bpy.types.World:
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Ribbon Signature World")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background is None:
        background = scene.world.node_tree.nodes.new("ShaderNodeBackground")
        output = scene.world.node_tree.nodes.get(
            "World Output"
        ) or scene.world.node_tree.nodes.new("ShaderNodeOutputWorld")
        scene.world.node_tree.links.new(
            background.outputs["Background"], output.inputs["Surface"]
        )
    return scene.world


def _ensure_compositor(scene: bpy.types.Scene) -> tuple[bpy.types.Node, bpy.types.Node]:
    compositor = bpy.data.node_groups.new(
        "Signature | exact background composite", "CompositorNodeTree"
    )
    compositor.interface.new_socket(
        name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
    )
    nodes = compositor.nodes
    render_layers = nodes.new("CompositorNodeRLayers")
    render_layers.name = "Ribbon Render"
    background = nodes.new("CompositorNodeRGB")
    background.name = "Theme Background"
    alpha_over = nodes.new("CompositorNodeAlphaOver")
    alpha_over.name = "Exact Background Composite"
    alpha_over.inputs["Factor"].default_value = 1.0
    group_output = nodes.new("NodeGroupOutput")
    compositor.links.new(background.outputs["Color"], alpha_over.inputs["Background"])
    compositor.links.new(
        render_layers.outputs["Image"], alpha_over.inputs["Foreground"]
    )
    compositor.links.new(alpha_over.outputs["Image"], group_output.inputs["Image"])
    scene.compositing_node_group = compositor
    return background, alpha_over


def _configure_theme(
    scene: bpy.types.Scene, theme_name: str, accent_names: list[str]
) -> dict[str, Any]:
    theme = CATPPUCCIN[theme_name]
    accents = [theme["accents"][name] for name in accent_names]
    palette = {
        "name": theme_name,
        "base_hex": theme["base"],
        "mantle_hex": theme["mantle"],
        "text_hex": theme["text"],
        "accent_names": accent_names,
        "accent_hex": accents,
        "accent_rgb": [hex_to_linear(color) for color in accents],
        "text_rgb": hex_to_linear(theme["text"]),
    }

    for material in bpy.data.materials:
        if material.name.startswith("Signature Ribbon "):
            shader = _material_shader(material)
            _set_principled_input(shader, "Roughness", theme["body"]["roughness"])
            _set_principled_input(
                shader, "Transmission Weight", theme["body"]["transmission"]
            )
            _set_principled_input(shader, "Alpha", theme["body"]["alpha"])
            _set_principled_input(
                shader, "Emission Strength", theme["body"]["emission"]
            )
            _set_principled_input(
                shader, "Emission Color", (*hex_to_linear(theme["mantle"]), 1.0)
            )
            material.diffuse_color = rgba(theme["mantle"], theme["body"]["alpha"])
        elif material.name.startswith("Signature Fiber "):
            shader = _material_shader(material)
            key = material.name.removeprefix("Signature Fiber ")
            if key == "soft_text" or key == "high_text":
                color = palette["text_rgb"]
            elif key.startswith(("soft_", "high_", "accent_")):
                suffix = int(key.rsplit("_", 1)[1])
                color = palette["accent_rgb"][suffix % len(accents)]
            else:
                raise RuntimeError(f"unknown signature material role: {key}")
            emission_roles = {
                "soft_text": "soft_text",
                "soft_0": "soft_secondary",
                "soft_1": "soft_blue",
                "soft_2": "soft_mauve",
                "high_text": "high_text",
                "high_0": "high_secondary",
                "accent_0": "accent_mauve",
                "accent_1": "accent_cool",
                "accent_2": "accent_blue",
                "accent_3": "accent_warm",
            }
            emission = theme["fiber_emission"][emission_roles[key]]
            _set_principled_input(shader, "Base Color", (*color, 1.0))
            _set_principled_input(shader, "Emission Color", (*color, 1.0))
            _set_principled_input(shader, "Emission Strength", emission)
            material.diffuse_color = (*color, 1.0)

    _apply_body_colors(scene, palette)
    world = _ensure_world(scene)
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = rgba(theme["base"])
    background.inputs["Strength"].default_value = 1.0

    for index, role in enumerate(theme["light_roles"]):
        light = bpy.data.objects.get(f"Signature Area Light {index + 1}")
        if light is None:
            continue
        light_hex = theme[role] if role in {"base", "text"} else theme["accents"][role]
        light.data.color = hex_to_linear(light_hex)

    compositor = scene.compositing_node_group
    if compositor is not None:
        bg_node = compositor.nodes.get("Theme Background")
        if bg_node is not None:
            bg_node.outputs["Color"].default_value = rgba(theme["base"])
    return palette


def _look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _make_light(
    name: str,
    location: tuple[float, float, float],
    energy: float,
    size: float,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = location
    _look_at(obj, Vector((0.0, 0.0, 0.0)))
    return obj


def _clear_scene(scene: bpy.types.Scene) -> None:
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    collection = bpy.data.collections.get("Signature Artwork")
    if collection is not None:
        bpy.data.collections.remove(collection)
    collection = bpy.data.collections.new("Signature Artwork")
    scene.collection.children.link(collection)


def _fit_geometry_to_frame(scene: bpy.types.Scene, width: int, height: int) -> float:
    coordinates = []
    for obj in scene.objects:
        if obj.type == "MESH":
            coordinates.extend(
                (obj.matrix_world @ vertex.co, 0.0) for vertex in obj.data.vertices
            )
        elif obj.type == "CURVE":
            coordinates.extend(
                (
                    obj.matrix_world @ Vector(point.co[:3]),
                    obj.data.bevel_depth * point.radius,
                )
                for spline in obj.data.splines
                for point in spline.points
            )
    if not coordinates:
        raise RuntimeError("cannot frame an empty signature scene")

    minimum = [
        min(point[axis] - radius for point, radius in coordinates) for axis in range(3)
    ]
    maximum = [
        max(point[axis] + radius for point, radius in coordinates) for axis in range(3)
    ]
    center = [(minimum[axis] + maximum[axis]) * 0.5 for axis in range(3)]
    frame_width = CAMERA_ORTHO_SCALE
    frame_height = CAMERA_ORTHO_SCALE * height / width
    half_width = frame_width * CAMERA_MARGIN * 0.5
    half_height = frame_height * CAMERA_MARGIN * 0.5
    extent_x = max(abs(minimum[0] - center[0]), abs(maximum[0] - center[0]))
    extent_z = max(abs(minimum[2] - center[2]), abs(maximum[2] - center[2]))
    scale = min(1.0, half_width / extent_x, half_height / extent_z)

    if scale < 1.0 or any(abs(value) > 1e-9 for value in center):
        for obj in scene.objects:
            if obj.type == "MESH":
                for vertex in obj.data.vertices:
                    vertex.co = tuple(
                        (vertex.co[axis] - center[axis]) * scale for axis in range(3)
                    )
                obj.data.update()
            elif obj.type == "CURVE":
                for spline in obj.data.splines:
                    for point in spline.points:
                        point.co = tuple(
                            (point.co[axis] - center[axis]) * scale for axis in range(3)
                        ) + (point.co[3],)
                obj.data.bevel_depth *= scale
        bpy.context.view_layer.update()
    return scale


def _create_scene(
    recipe: dict[str, Any],
    quality: str,
    threads: int,
    background_mode: str = "theme",
) -> dict[str, Any]:
    if background_mode not in BACKGROUND_MODES:
        raise ValueError("background mode must be 'theme' or 'transparent'")
    scene = bpy.context.scene
    _clear_scene(scene)
    collection = bpy.data.collections["Signature Artwork"]
    width, height = FINAL_SIZE if quality == "final" else PREVIEW_SIZE
    transformed_paths, _ = _transform_paths(recipe)

    body_materials = {
        family: _make_mesh_material(f"Signature Ribbon {family}")
        for family in RIBBON_SPECS
    }
    fiber_materials = {
        key: _make_fiber_material(f"Signature Fiber {key}")
        for key in FIBER_MATERIAL_KEYS
    }
    ribbon_objects = []
    frames_by_family = {}
    for ribbon_name, spec in RIBBON_SPECS.items():
        frames = _strand_frames(
            transformed_paths[ribbon_name], spec["phase"], spec["roll"], spec["cycles"]
        )
        frames_by_family[ribbon_name] = frames
        ribbon_objects.append(
            _make_ribbon_mesh(
                f"Translucent Support {ribbon_name}",
                frames,
                spec["width"],
                0.10 if ribbon_name != "drift" else 0.12,
                body_materials[ribbon_name],
                collection,
                ribbon_name,
            )
        )

    strands, high_strands, overlays = _add_strand_clusters(
        collection,
        fiber_materials,
        frames_by_family,
        recipe["parameters"]["strands"],
        recipe["seeds"]["strands"],
    )
    if len(ribbon_objects) != 3 or strands != 52 or overlays != 6:
        raise RuntimeError(
            "signature geometry counts differ from the approved composition"
        )
    fit_scale = _fit_geometry_to_frame(scene, width, height)

    camera_data = bpy.data.cameras.new("Signature Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = CAMERA_ORTHO_SCALE
    camera_data.lens = 50.0
    camera = bpy.data.objects.new("Signature Camera", camera_data)
    collection.objects.link(camera)
    camera.location = (0.0, -17.5, 0.0)
    camera.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.camera = camera

    for index, (location, energy, size) in enumerate(
        (
            ((-4.8, -5.5, 6.8), 820.0, 7.0),
            ((4.2, -4.0, 1.2), 410.0, 6.5),
            ((0.4, 2.8, 5.2), 620.0, 5.0),
        ),
        start=1,
    ):
        _make_light(f"Signature Area Light {index}", location, energy, size, collection)

    _ensure_world(scene)
    if background_mode == "theme":
        _ensure_compositor(scene)
    else:
        scene.compositing_node_group = None
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48 if quality == "final" else 16
    scene.cycles.preview_samples = 16
    scene.cycles.use_animated_seed = False
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 2
    scene.cycles.seed = int(recipe["seeds"]["geometry"][:8], 16) & 0x7FFFFFFF
    scene.render.threads_mode = "FIXED"
    scene.render.threads = threads
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = (
        "RGBA" if background_mode == "transparent" else "RGB"
    )
    scene.render.image_settings.color_depth = "8"
    scene.render.use_file_extension = True
    scene.render.film_transparent = True
    scene.render.dither_intensity = 0.0
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.render.use_compositing = background_mode == "theme"
    scene.render.use_sequencer = False
    scene.render.resolution_percentage = 100
    scene.render.filepath = "//signature.png"
    bpy.context.preferences.filepaths.save_version = 0

    for obj in scene.objects:
        obj.select_set(False)
    _assert_finite_geometry(scene)
    _assert_framing(scene, width, height)
    return {
        "scene": scene,
        "camera": camera,
        "fit_scale": fit_scale,
        "counts": {
            "supports": len(ribbon_objects),
            "fibres": strands,
            "higher_contrast_fibres": high_strands,
            "overlays": overlays,
        },
        "render_size": {"width": width, "height": height},
    }


def _assert_finite_geometry(scene: bpy.types.Scene) -> None:
    for obj in scene.objects:
        if obj.type == "MESH":
            for vertex in obj.data.vertices:
                if not all(math.isfinite(value) for value in vertex.co):
                    raise RuntimeError(f"non-finite mesh coordinate in {obj.name}")
        elif obj.type == "CURVE":
            for spline in obj.data.splines:
                for point in spline.points:
                    if not all(math.isfinite(value) for value in point.co):
                        raise RuntimeError(f"non-finite curve coordinate in {obj.name}")
                    if not math.isfinite(point.radius):
                        raise RuntimeError(f"non-finite curve radius in {obj.name}")


def _assert_framing(scene: bpy.types.Scene, width: int, height: int) -> None:
    frame_width = CAMERA_ORTHO_SCALE
    frame_height = CAMERA_ORTHO_SCALE * height / width
    x_limit = frame_width * 0.5 * CAMERA_MARGIN
    z_limit = frame_height * 0.5 * CAMERA_MARGIN
    for obj in scene.objects:
        if obj.type == "MESH":
            coordinates = [
                (vertex.co.x, vertex.co.z, 0.0) for vertex in obj.data.vertices
            ]
        elif obj.type == "CURVE":
            coordinates = [
                (point.co.x, point.co.z, obj.data.bevel_depth * point.radius)
                for spline in obj.data.splines
                for point in spline.points
            ]
        else:
            continue
        for x, z, radius in coordinates:
            if abs(x) + radius > x_limit + 1e-5 or abs(z) + radius > z_limit + 1e-5:
                raise RuntimeError(
                    f"signature geometry exceeds safe camera frame: {obj.name}"
                )


def _hash_value(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def geometry_fingerprint(scene: bpy.types.Scene) -> str:
    records = []
    for obj in sorted(scene.objects, key=lambda item: item.name):
        if obj.type == "MESH":
            data = {
                "kind": "mesh",
                "name": obj.name,
                "vertices": [
                    [round(float(component), 9) for component in vertex.co]
                    for vertex in obj.data.vertices
                ],
                "faces": [list(polygon.vertices) for polygon in obj.data.polygons],
            }
        elif obj.type == "CURVE":
            data = {
                "kind": "curve",
                "name": obj.name,
                "bevel_depth": round(float(obj.data.bevel_depth), 9),
                "bevel_resolution": obj.data.bevel_resolution,
                "splines": [
                    {
                        "type": spline.type,
                        "cyclic": bool(spline.use_cyclic_u),
                        "points": [
                            [round(float(component), 9) for component in point.co]
                            + [round(float(point.radius), 9)]
                            for point in spline.points
                        ],
                    }
                    for spline in obj.data.splines
                ],
            }
        else:
            continue
        data["location"] = [round(float(component), 9) for component in obj.location]
        data["rotation"] = [
            round(float(component), 9) for component in obj.rotation_euler
        ]
        data["scale"] = [round(float(component), 9) for component in obj.scale]
        records.append(data)
    return _hash_value(records)


def camera_fingerprint(scene: bpy.types.Scene) -> str:
    camera = scene.camera
    record = {
        "name": camera.name if camera else None,
        "type": camera.data.type if camera else None,
        "ortho_scale": round(float(camera.data.ortho_scale), 9) if camera else None,
        "location": [round(float(component), 9) for component in camera.location]
        if camera
        else None,
        "rotation": [round(float(component), 9) for component in camera.rotation_euler]
        if camera
        else None,
        "scale": [round(float(component), 9) for component in camera.scale]
        if camera
        else None,
        "lens": round(float(camera.data.lens), 9) if camera else None,
        "resolution": [
            scene.render.resolution_x,
            scene.render.resolution_y,
            scene.render.resolution_percentage,
        ],
        "pixel_aspect": [scene.render.pixel_aspect_x, scene.render.pixel_aspect_y],
    }
    return _hash_value(record)


def render_settings(scene: bpy.types.Scene) -> dict[str, Any]:
    return {
        "engine": scene.render.engine,
        "device": scene.cycles.device,
        "samples": scene.cycles.samples,
        "denoising": scene.cycles.use_denoising,
        "seed": scene.cycles.seed,
        "animated_seed": scene.cycles.use_animated_seed,
        "max_bounces": scene.cycles.max_bounces,
        "diffuse_bounces": scene.cycles.diffuse_bounces,
        "glossy_bounces": scene.cycles.glossy_bounces,
        "threads_mode": scene.render.threads_mode,
        "threads": scene.render.threads,
        "resolution": [
            scene.render.resolution_x,
            scene.render.resolution_y,
            scene.render.resolution_percentage,
        ],
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "color_depth": scene.render.image_settings.color_depth,
        "film_transparent": scene.render.film_transparent,
        "dither_intensity": scene.render.dither_intensity,
        "pixel_aspect": [scene.render.pixel_aspect_x, scene.render.pixel_aspect_y],
        "view_transform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": scene.view_settings.exposure,
        "gamma": scene.view_settings.gamma,
        "compositing": scene.render.use_compositing,
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_or_nested(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def validate_job(job_path: Path, *, overwrite: bool = False) -> dict[str, Any]:
    if not job_path.is_absolute() or not job_path.is_file():
        raise ValueError("--job must name an existing absolute JSON file")
    with job_path.open("r", encoding="utf-8") as source:
        job = json.load(source)
    if not isinstance(job, dict) or job.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("job must be an object with schema_version 1")
    if job.get("quality") not in {"preview", "final"}:
        raise ValueError("quality must be 'preview' or 'final'")
    background = job.get("background", "theme")
    if background not in BACKGROUND_MODES:
        raise ValueError("background must be 'theme' or 'transparent'")
    threads = job.get("threads")
    if type(threads) is not int or not 1 <= threads <= THREAD_CAP:
        raise ValueError(f"threads must be an integer from 1 to {THREAD_CAP}")
    if type(overwrite) is not bool:
        raise ValueError("overwrite must be an explicit boolean command-line option")

    recipe = job.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError("job recipe must be an object")
    recipe_options = {}
    if "assigned_family" in recipe:
        assigned_family = recipe["assigned_family"]
        if not isinstance(assigned_family, str) or assigned_family not in FAMILIES:
            raise ValueError(f"assigned_family must be one of {FAMILIES!r}")
        recipe_options["assigned_family"] = assigned_family
    try:
        expected = make_recipe(
            recipe.get("canonical_path"), recipe.get("variation"), **recipe_options
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"invalid recipe path, variation, or family: {error}"
        ) from error
    recipe_fields = (
        "version",
        "canonical_path",
        "variation",
        "seed",
        "family",
        "accents",
        "seeds",
        "parameters",
    )
    if "assigned_family" in expected:
        recipe_fields += ("assigned_family",)
    for field in recipe_fields:
        if recipe.get(field) != expected[field]:
            raise ValueError(
                f"recipe field {field!r} does not match its deterministic recipe"
            )

    workspace_value = job.get("workspace_root")
    if not isinstance(workspace_value, str) or not workspace_value:
        raise ValueError(
            "workspace_root must be a required absolute CLI workspace path"
        )
    workspace_candidate = Path(workspace_value)
    if not workspace_candidate.is_absolute():
        raise ValueError("workspace_root must be absolute")
    workspace_root = workspace_candidate.resolve()
    if workspace_root == Path(workspace_root.anchor):
        raise ValueError("workspace_root must not be a filesystem root")
    if _same_or_nested(workspace_root, REPO_ROOT):
        raise ValueError(
            "workspace_root must be wholly outside and separate from the repository"
        )
    if not workspace_root.exists() or not workspace_root.is_dir():
        raise ValueError("workspace_root must already exist")

    output_value = job.get("output_dir")
    if not isinstance(output_value, str) or not output_value:
        raise ValueError("output_dir must be a non-empty absolute directory path")
    output_dir = Path(output_value)
    if not output_dir.is_absolute():
        raise ValueError("output_dir must be absolute")
    current = output_dir
    while True:
        if current.is_symlink():
            raise ValueError(f"output_dir path contains a symlink: {current}")
        if current.parent == current:
            break
        current = current.parent
    output_dir = output_dir.resolve()
    if output_dir == workspace_root or workspace_root not in output_dir.parents:
        raise ValueError(
            "output_dir must be a strict descendant of workspace_root after symlink resolution"
        )
    if _same_or_nested(output_dir, REPO_ROOT):
        raise ValueError("output_dir must be wholly outside the repository")
    slug = recipe["canonical_path"].removeprefix("/posts/").removesuffix("/")
    expected_output_dir = workspace_root / slug / f"recipe-v{recipe['version']}"
    if "assigned_family" in recipe:
        expected_output_dir /= f"family-{recipe['family']}"
    if background == "transparent":
        expected_output_dir /= "background-transparent"
    expected_output_dir = (
        expected_output_dir / f"variation-{recipe['variation']}" / job["quality"]
    ).resolve()
    if output_dir != expected_output_dir:
        raise ValueError(
            "output_dir must use this post's versioned family-assignment path under workspace_root"
        )
    if not output_dir.exists() or not output_dir.is_dir():
        raise ValueError(
            "output_dir must already exist; the wrapper owns directory creation"
        )
    runner_job_path = output_dir / "job.json"
    runner_job_matches = False
    if runner_job_path.exists():
        if runner_job_path.is_symlink() or not runner_job_path.is_file():
            raise ValueError("output_dir/job.json must be a regular job file")
        try:
            with runner_job_path.open("r", encoding="utf-8") as source:
                runner_job = json.load(source)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                f"could not validate output_dir/job.json: {error}"
            ) from error
        runner_job_matches = (
            isinstance(runner_job, dict)
            and runner_job.get("schema_version") == SCHEMA_VERSION
            and runner_job.get("recipe") == recipe
            and runner_job.get("quality") == job["quality"]
            and runner_job.get("background", "theme") == background
            and runner_job.get("output_dir") == str(output_dir)
            and runner_job.get("workspace_root") == str(workspace_root)
            and runner_job.get("threads") == threads
        )
        if not runner_job_matches:
            raise ValueError("output_dir/job.json does not match this signature job")
    output_paths = [output_dir / name for name in OUTPUT_NAMES]
    for path in output_paths:
        if path.is_symlink():
            raise ValueError(f"signature output must not be a symlink: {path.name}")
        if path.exists() and not path.is_file():
            raise ValueError(
                f"signature output path must be a regular file: {path.name}"
            )
    collisions = [path.name for path in output_paths if path.exists()]
    if collisions and not overwrite:
        raise FileExistsError(
            f"signature outputs already exist; explicit --overwrite is required: {', '.join(collisions)}"
        )
    job["recipe"] = recipe
    job["background"] = background
    job["output_dir"] = str(output_dir)
    job["workspace_root"] = str(workspace_root)
    job["threads"] = threads
    return job


def _commit_staged_outputs(
    staging_dir: Path, output_dir: Path, *, overwrite: bool
) -> None:
    staged_paths = {name: staging_dir / name for name in OUTPUT_NAMES}
    final_paths = {name: output_dir / name for name in OUTPUT_NAMES}
    for name, path in staged_paths.items():
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"staged output is missing or unsafe: {name}")
    for name, path in final_paths.items():
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError(f"final output path is not a regular file: {name}")

    collisions = [name for name, path in final_paths.items() if path.exists()]
    if collisions and not overwrite:
        raise FileExistsError(
            f"signature outputs appeared during rendering; explicit --overwrite is required: {', '.join(collisions)}"
        )

    backup_dir = staging_dir / ".previous"
    moved_previous = []
    installed = []
    try:
        if collisions:
            backup_dir.mkdir()
            for name in collisions:
                os.replace(final_paths[name], backup_dir / name)
                moved_previous.append(name)
        for name in OUTPUT_NAMES:
            os.replace(staged_paths[name], final_paths[name])
            installed.append(name)
    except Exception as error:
        rollback_errors = []
        for name in reversed(installed):
            path = final_paths[name]
            try:
                if path.is_symlink() or (path.exists() and not path.is_file()):
                    raise RuntimeError(
                        f"cannot safely roll back unexpected output path: {path}"
                    )
                if path.exists():
                    path.unlink()
            except Exception as rollback_error:
                rollback_errors.append(f"remove {name}: {rollback_error}")
        for name in reversed(moved_previous):
            backup = backup_dir / name
            final = final_paths[name]
            try:
                if final.exists() or final.is_symlink():
                    raise RuntimeError(
                        f"cannot restore previous output over unexpected path: {final}"
                    )
                os.replace(backup, final)
            except Exception as rollback_error:
                rollback_errors.append(f"restore {name}: {rollback_error}")
        if rollback_errors:
            raise RuntimeError(
                f"output commit failed and rollback was incomplete: {'; '.join(rollback_errors)}"
            ) from error
        raise

    for name in moved_previous:
        (backup_dir / name).unlink()
    if backup_dir.exists():
        backup_dir.rmdir()
    staging_dir.rmdir()


def render_pair(job: dict[str, Any], *, overwrite: bool = False) -> dict[str, Any]:
    background = job.get("background", "theme")
    scene_info = _create_scene(
        job["recipe"], job["quality"], job["threads"], background
    )
    scene = scene_info["scene"]
    base_geometry_fingerprint = geometry_fingerprint(scene)
    base_camera_fingerprint = camera_fingerprint(scene)
    base_render_settings = render_settings(scene)
    output_dir = Path(job["output_dir"])
    staging_dir = Path(tempfile.mkdtemp(prefix=".signature-stage-", dir=output_dir))
    theme_records = {}

    for theme_name in ("latte", "mocha"):
        palette = _configure_theme(scene, theme_name, job["recipe"]["accents"])
        if geometry_fingerprint(scene) != base_geometry_fingerprint:
            raise RuntimeError(f"{theme_name} theme setup changed geometry")
        if camera_fingerprint(scene) != base_camera_fingerprint:
            raise RuntimeError(f"{theme_name} theme setup changed camera")
        if render_settings(scene) != base_render_settings:
            raise RuntimeError(f"{theme_name} theme setup changed render settings")

        png_path = staging_dir / f"{theme_name}.png"
        blend_path = staging_dir / f"{theme_name}.blend"
        final_png_path = output_dir / png_path.name
        scene.render.filepath = str(final_png_path)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False)
        scene.render.filepath = str(png_path)
        bpy.ops.render.render(write_still=True)
        scene.render.filepath = str(final_png_path)
        if not png_path.is_file() or png_path.stat().st_size <= 0:
            raise RuntimeError(f"Blender did not produce {png_path.name}")
        if not blend_path.is_file() or blend_path.stat().st_size <= 0:
            raise RuntimeError(f"Blender did not produce {blend_path.name}")
        if geometry_fingerprint(scene) != base_geometry_fingerprint:
            raise RuntimeError(f"{theme_name} render changed geometry")
        theme_records[theme_name] = {
            "png": png_path.name,
            "blend": blend_path.name,
            "palette": {
                "accents": palette["accent_names"],
                "hex": palette["accent_hex"],
                "background": palette["base_hex"],
            },
            "png_sha256": _file_sha256(png_path),
            "blend_sha256": _file_sha256(blend_path),
        }

    if geometry_fingerprint(scene) != base_geometry_fingerprint:
        raise RuntimeError("paired renders do not share identical geometry")
    if camera_fingerprint(scene) != base_camera_fingerprint:
        raise RuntimeError("paired renders do not share an identical camera")
    if render_settings(scene) != base_render_settings:
        raise RuntimeError("paired renders do not share render settings")

    width, height = (
        scene_info["render_size"]["width"],
        scene_info["render_size"]["height"],
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator_version": "1",
        "recipe": job["recipe"],
        "quality": job["quality"],
        "background": background,
        "workspace_root": job["workspace_root"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
        "python_version": sys.version.split()[0],
        "thread_cap": job["threads"],
        "render_size": {"width": width, "height": height},
        "geometry_family": job["recipe"]["family"],
        "geometry_counts": scene_info["counts"],
        "fit_scale": round(scene_info["fit_scale"], 8),
        "geometry_fingerprint": base_geometry_fingerprint,
        "camera_fingerprint": base_camera_fingerprint,
        "render_settings": base_render_settings,
        "themes": theme_records,
    }
    manifest_path = staging_dir / "manifest.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(
            manifest,
            destination,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        destination.write("\n")
    _commit_staged_outputs(staging_dir, output_dir, overwrite=overwrite)
    print(f"Signature pair written to {output_dir}")
    print(f"Geometry fingerprint: {base_geometry_fingerprint}")
    return manifest


def _parse_job_argument(argv: list[str] | None = None) -> tuple[Path, bool]:
    arguments = sys.argv if argv is None else argv
    if "--" in arguments:
        arguments = arguments[arguments.index("--") + 1 :]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--job", required=True, help="absolute path to a version-1 JSON job file"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace only the known outputs in the validated workspace",
    )
    parsed = parser.parse_args(arguments)
    path = Path(parsed.job)
    if not path.is_absolute():
        raise ValueError("--job must be an absolute path")
    return path, parsed.overwrite


def main(argv: list[str] | None = None) -> int:
    try:
        job_path, overwrite = _parse_job_argument(argv)
        job = validate_job(job_path, overwrite=overwrite)
        render_pair(job, overwrite=overwrite)
    except (
        Exception
    ) as error:  # Blender background mode should emit a clear nonzero result.
        print(f"signature scene worker failed: {error}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    main()
