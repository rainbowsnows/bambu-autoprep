"""Deterministic example models. All lengths are millimetres; no model service required."""
from pathlib import Path
import math
import numpy as np
import trimesh


def dimensions(values, defaults):
    extra = set(values) - set(defaults)
    if extra:
        raise ValueError("Unknown model dimension(s): " + ", ".join(sorted(extra)))
    out = {**defaults, **values}
    if any(not math.isfinite(float(v)) or not 1 <= float(v) <= 250 for v in out.values()):
        raise ValueError("Dimensions must be finite and between 1 and 250 mm")
    return {k: float(v) for k, v in out.items()}


def box(extents, center):
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(center)
    return mesh


def build_model(template: str, parameters: dict):
    if template == "ghost":
        d = dimensions(parameters, {"height": 40, "width": 30})
        r = d["width"] / 2
        h = d["height"]
        profile = np.array([[0,0],[r,0],[r,h*.52],[r*.96,h*.66],
                            [r*.8,h*.8],[r*.5,h*.94],[0,h]])
        body = trimesh.creation.revolve(profile, sections=96)
        cuts = []
        for x,z,rad in [(-r*.33,h*.66,r*.14),(r*.33,h*.66,r*.14),(0,h*.49,r*.18)]:
            eye = trimesh.creation.icosphere(subdivisions=3, radius=rad)
            eye.apply_translation([x,-r*.96,z])
            cuts.append(eye)
        mesh = trimesh.boolean.difference([body, *cuts], engine="manifold")
        note = "Solid rounded ghost with recessed face and flat base; single colour. No separate pieces."
    elif template == "cable-holder":
        d = dimensions(parameters, {"width": 28, "depth": 18, "height": 14, "cable_diameter": 5})
        w,l,h = d["width"],d["depth"],d["height"]
        diameter = d["cable_diameter"]
        if diameter > min(w-4,h-3):
            raise ValueError("Cable groove needs at least 2 mm of surrounding material")
        body = box([w,l,h], [0,0,h/2])
        groove = trimesh.creation.cylinder(radius=(diameter+0.6)/2, height=l+2, sections=64)
        groove.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0]))
        groove.apply_translation([0,0,h])
        mesh = trimesh.boolean.difference([body,groove], engine="manifold")
        note = "Open desktop cable groove with 0.6 mm diameter clearance; adhesive mounting optional, not a snap-fit clip."
    elif template == "phone-stand":
        d = dimensions(parameters, {"width": 70, "depth": 85, "height": 70, "thickness": 5})
        w,l,h,t = d["width"],d["depth"],d["height"],d["thickness"]
        if t < 3 or t > min(w,l,h)/4:
            raise ValueError("Use 3 mm or thicker walls with space for the phone")
        base = box([w,l,t],[0,0,t/2])
        back = box([w,t,h],[0,0,0])
        back.apply_transform(trimesh.transformations.rotation_matrix(-np.deg2rad(15),[1,0,0]))
        back.apply_translation([0,0,t+h/2-1])
        lip = box([w,t,12],[0,-l/2+t/2,t+5])
        mesh = trimesh.boolean.union([base,back,lip], engine="manifold")
        note = "Wide desk stand with 15 degree reclined back and front lip; fit and stability need a trial print."
    else:
        raise ValueError("Templates: ghost, cable-holder, phone-stand. Other objects need task-specific CAD/mesh generation.")
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh)
    if not mesh.is_watertight or not mesh.is_volume or len(mesh.split()) != 1:
        raise ValueError("Generated model failed closed-volume or connected-part validation")
    mesh.apply_translation([0,0,-mesh.bounds[0,2]])
    return mesh, {"template": template, "parameters_mm": d, "design_note": note,
                  "watertight": True, "connected_components": 1, "units": "mm"}
