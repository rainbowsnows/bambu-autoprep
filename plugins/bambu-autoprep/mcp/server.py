from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:
    raise SystemExit(
        "Missing MCP package. Run: python -m pip install -r requirements.txt"
    ) from e

mcp = FastMCP("3D Print")

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
EXAMPLE_CONFIG = HERE / "config.example.json"

SAFE_PROCESS_KEYS = {
    "layer_height",
    "wall_loops",
    "top_shell_layers",
    "top_shell_thickness",
    "bottom_shell_layers",
    "bottom_shell_thickness",
    "sparse_infill_density",
    "sparse_infill_pattern",
    "enable_support",
    "support_type",
    "support_style",
    "support_threshold_angle",
    "support_on_build_plate_only",
    "brim_type",
    "brim_width",
    "brim_object_gap",
    "seam_position",
    "detect_thin_wall",
    "detect_overhang_wall",
    "ironing_type",
}

def load_config() -> dict[str, Any]:
    p = Path(os.environ.get("BAMBU_AUTOPREP_CONFIG", str(CONFIG_PATH)))
    p = p if p.exists() else EXAMPLE_CONFIG
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

def find_bambu_executable(explicit: Optional[str] = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))

    for name in ("bambu-studio", "bambu-studio.exe", "BambuStudio.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    if os.name == "nt":
        candidates += [
            Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe"),
            Path(r"C:\Program Files\Bambu Studio\BambuStudio.exe"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Bambu Studio" / "bambu-studio.exe",
        ]
    elif sys_platform() == "darwin":
        candidates += [
            Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
            Path("/Applications/Bambu Studio.app/Contents/MacOS/BambuStudio"),
        ]

    for p in candidates:
        if p and p.exists() and p.is_file():
            return p.resolve()

    raise FileNotFoundError(
        "Bambu Studio executable was not found. Set bambu_studio_path in mcp/config.json."
    )

def sys_platform() -> str:
    import sys
    return sys.platform

def find_profile_root(exe: Path, explicit: Optional[str] = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))

    exe_dir = exe.parent
    candidates += [
        exe_dir / "resources" / "profiles" / "BBL",
        exe_dir.parent / "resources" / "profiles" / "BBL",
        exe_dir / ".." / "Resources" / "profiles" / "BBL",
        exe_dir / ".." / "Resources" / "resources" / "profiles" / "BBL",
    ]

    if sys_platform() == "darwin":
        # executable is usually .../Contents/MacOS/BambuStudio
        contents = exe_dir.parent
        candidates += [
            contents / "Resources" / "profiles" / "BBL",
            contents / "Resources" / "resources" / "profiles" / "BBL",
        ]

    for p in candidates:
        p = p.resolve()
        if (p / "machine").exists() and (p / "process").exists() and (p / "filament").exists():
            return p

    raise FileNotFoundError(
        "Bambu BBL profile folder was not found. Set profile_root in mcp/config.json."
    )

def normalize_name(s: str) -> str:
    return "".join(ch.lower() for ch in s if ch.isalnum())

def find_profile_file(profile_root: Path, category: str, requested: str) -> Path:
    folder = profile_root / category
    if not folder.exists():
        raise FileNotFoundError(f"Profile category not found: {folder}")

    files = list(folder.rglob("*.json"))
    exact = []
    target = normalize_name(requested)

    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        display = str(data.get("name") or f.stem)
        if display == requested or f.stem == requested:
            return f
        if normalize_name(display) == target or normalize_name(f.stem) == target:
            exact.append(f)

    if exact:
        return exact[0]

    raise FileNotFoundError(f'Could not find {category} profile matching "{requested}".')

def re_split(s: str) -> list[str]:
    import re
    return re.findall(r"[A-Za-z0-9.]+", s)

def build_name_index(folder: Path) -> dict[str, Path]:
    idx: dict[str, Path] = {}
    for f in folder.rglob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        name = str(data.get("name") or f.stem)
        idx[name] = f
        idx[f.stem] = f
    return idx

def flatten_profile(path: Path, folder: Path, cache=None, visiting=None) -> dict[str, Any]:
    if cache is None:
        cache = {}
    key = str(path.resolve())
    if key in cache:
        return dict(cache[key])

    visiting = set() if visiting is None else visiting
    if key in visiting:
        raise ValueError("Cyclic profile inheritance: " + path.name)
    visiting.add(key)
    data = json.loads(path.read_text(encoding="utf-8"))
    parent_name = data.get("inherits")
    merged: dict[str, Any] = {}

    if parent_name:
        index = build_name_index(folder)
        parent = index.get(str(parent_name))
        if parent is None:
            # fallback normalized lookup
            target = normalize_name(str(parent_name))
            for k, p in index.items():
                if normalize_name(k) == target:
                    parent = p
                    break
        if parent is None:
            raise FileNotFoundError(
                f'Cannot resolve inherited profile "{parent_name}" for {path.name}'
            )
        merged.update(flatten_profile(parent, folder, cache, visiting))

    index = build_name_index(folder)
    for include_name in data.get("include", []):
        included = index.get(include_name)
        if included is None:
            raise FileNotFoundError(f'Cannot resolve included profile "{include_name}"')
        merged.update(flatten_profile(included, folder, cache, visiting))
    merged.update(data)
    merged.pop("inherits", None)
    merged.pop("include", None)
    visiting.remove(key)
    cache[key] = dict(merged)
    return merged

def safe_apply_process_overrides(process: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = dict(process)
    bad = [k for k in overrides if k not in SAFE_PROCESS_KEYS]
    if bad:
        raise ValueError(
            "Unsupported process override(s): " + ", ".join(sorted(bad)) +
            ". This tool intentionally blocks machine-motion, firmware, and G-code overrides."
        )
    for k, v in overrides.items():
        if not isinstance(v, (str, bool, int, float)):
            raise ValueError(f"Override {k} must be scalar")
        ranges = {"layer_height": (0.04, 0.6), "wall_loops": (1, 20),
                  "top_shell_layers": (0, 30), "bottom_shell_layers": (0, 30),
                  "brim_width": (0, 30), "support_threshold_angle": (0, 90)}
        if k in ranges:
            n = float(v)
            if not math.isfinite(n) or not ranges[k][0] <= n <= ranges[k][1]:
                raise ValueError(f"Override {k} is outside its conservative range")
        if k == "sparse_infill_density":
            n = float(str(v).rstrip("%"))
            if not math.isfinite(n) or not 0 <= n <= 100:
                raise ValueError("Infill must be between 0 and 100 percent")
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif isinstance(v, (int, float)):
            out[k] = str(v)
        else:
            out[k] = v
    return out

def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def extract_preview(three_mf: Path, dest: Path) -> Optional[Path]:
    try:
        with zipfile.ZipFile(three_mf, "r") as z:
            pngs = [n for n in z.namelist() if n.lower().endswith(".png")]
            if not pngs:
                return None
            # Prefer explicit thumbnail/plate images, otherwise the largest PNG.
            ranked = []
            for n in pngs:
                info = z.getinfo(n)
                bonus = 10_000_000 if ("thumb" in n.lower() or "plate" in n.lower()) else 0
                ranked.append((bonus + info.file_size, n))
            ranked.sort(reverse=True)
            chosen = ranked[0][1]
            dest.write_bytes(z.read(chosen))
            return dest
    except Exception:
        return None

def read_slice_metadata(three_mf: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(three_mf, "r") as z:
            names = z.namelist()
            candidates = [
                n for n in names
                if n.lower().endswith(("slice_info.config", "slice_info.json", "project_settings.config"))
            ]
            for n in candidates[:3]:
                raw = z.read(n)
                text = raw.decode("utf-8", errors="ignore")
                out[n] = text[:12000]
    except Exception:
        pass
    return out

def load_mesh(model: Path):
    """Read geometry only. Drop imported settings and custom G-code before slicing."""
    import numpy as np
    import trimesh
    if not model.is_file() or model.suffix.lower() not in {".stl", ".obj", ".3mf", ".step", ".stp"}:
        raise ValueError("Provide STL, OBJ, 3MF or STEP (optional CadQuery)")
    if model.stat().st_size > 200 * 1024 * 1024:
        raise ValueError("Input exceeds 200 MiB")
    if model.suffix.lower() == ".3mf":
        with zipfile.ZipFile(model) as z:
            if sum(i.file_size for i in z.infolist()) > 400 * 1024 * 1024:
                raise ValueError("3MF exceeds unpacked size limit")
    if model.suffix.lower() in {".step", ".stp"}:
        try:
            import cadquery as cq
        except ImportError as exc:
            raise ValueError("STEP requires optional CadQuery on the MCP host") from exc
        solid = cq.importers.importStep(str(model)).val()
        vertices, faces = solid.tessellate(0.1)
        mesh = trimesh.Trimesh(vertices=[v.toTuple() for v in vertices], faces=faces, process=True)
    else:
        mesh = trimesh.load(model, force="mesh", process=True)
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError("No triangle mesh found")
    if len(mesh.faces) > 2_000_000 or not np.isfinite(mesh.vertices).all() or np.any(mesh.extents <= 0):
        raise ValueError("Invalid or overly complex geometry")
    if mesh.units and mesh.units != "mm":
        mesh.convert_units("mm")
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh, multibody=True)
    if not mesh.is_watertight:
        trimesh.repair.fill_holes(mesh)
    return mesh


@mcp.tool()
def analyze_model(model_path: str) -> dict[str, Any]:
    """Inspect geometry in supplied orientation. STL/OBJ units are assumed mm."""
    import numpy as np
    mesh = load_mesh(Path(model_path).expanduser().resolve())
    above = mesh.triangles_center[:, 2] > mesh.bounds[0, 2] + 0.3
    downward = mesh.face_normals[:, 2] < -np.cos(np.deg2rad(45))
    bed = np.all(mesh.triangles[:, :, 2] <= mesh.bounds[0, 2] + 0.05, axis=1)
    return {"dimensions_mm": mesh.extents.tolist(), "faces": len(mesh.faces),
            "watertight": bool(mesh.is_watertight), "units": "mm",
            "connected_components": len(mesh.split(only_watertight=False)),
            "bed_contact_area_mm2": float(mesh.area_faces[bed].sum()),
            "support_candidate_area_mm2": float(mesh.area_faces[above & downward].sum()),
            "orientation_note": "Estimate is for input orientation; bridges need review",
            "thickness_note": "Wall thickness, tiny details and strength require construction/sliced-path review",
            "warnings": [] if mesh.is_watertight else ["Mesh is not watertight; repair before slicing"]}


def render_geometry_preview(mesh, dest: Path) -> None:
    from presentation import render_poster
    render_poster(mesh, dest)


def validate_sliced_3mf(path: Path) -> None:
    with zipfile.ZipFile(path) as z:
        if z.testzip():
            raise ValueError("Exported 3MF contains a corrupt ZIP member")
        names = z.namelist()
        if "[Content_Types].xml" not in names or not any(n.lower().endswith(".model") for n in names):
            raise ValueError("Export contains no 3MF model")
        if not any(n.lower().endswith(".gcode") and z.getinfo(n).file_size > 0 for n in names):
            raise ValueError("Export contains no sliced G-code")


@mcp.tool()
def generate_model(template: str, output_dir: str, parameters: Optional[dict[str, float]] = None) -> dict[str, Any]:
    """Generate real STL and render for ghost, cable-holder or phone-stand; dimensions in mm."""
    from geometry import build_model
    mesh, report = build_model(template, parameters or {})
    outdir = Path(output_dir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    model = outdir / f"{template}.stl"
    preview = outdir / "model_preview.png"
    mesh.export(model)
    render_geometry_preview(mesh, preview)
    write_json(outdir / "model_report.json", report)
    return {"model_file": str(model), "preview_png": str(preview), "report": report,
            "analysis": analyze_model(str(model)), "printer_started": False}


from design import generate_custom_model
mcp.tool()(generate_custom_model)


from unsliced import prepare_unsliced_3mf
mcp.tool()(prepare_unsliced_3mf)


@mcp.tool()
def health_check() -> dict[str, Any]:
    """Discover local slicer/profiles. No physical printer connection."""
    cfg = load_config()
    try:
        exe = find_bambu_executable(cfg.get("bambu_studio_path"))
        root = find_profile_root(exe, cfg.get("profile_root"))
    except FileNotFoundError as exc:
        return {"ok": False, "reason": str(exc), "printer_start_supported": False}
    return {"ok": True, "bambu_studio": str(exe), "profile_root": str(root),
            "defaults": cfg.get("defaults", {}), "printer_start_supported": False}

@mcp.tool()
def list_matching_profiles(
    category: str,
    contains: str,
    limit: int = 20,
) -> list[str]:
    """List installed Bambu profile names matching text. category: machine/process/filament."""
    if category not in {"machine", "process", "filament"}:
        raise ValueError("category must be machine, process, or filament")
    cfg = load_config()
    exe = find_bambu_executable(cfg.get("bambu_studio_path"))
    root = find_profile_root(exe, cfg.get("profile_root"))
    folder = root / category
    needle = normalize_name(contains)
    found = []
    for f in folder.rglob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            name = str(data.get("name") or f.stem)
        except Exception:
            continue
        if needle in normalize_name(name):
            found.append(name)
    return sorted(set(found))[:max(1, min(limit, 100))]

@mcp.tool()
def prepare_3mf(
    model_path: str,
    output_dir: str,
    machine_profile: str,
    process_profile: str,
    filament_profile: str,
    process_overrides: Optional[dict[str, Any]] = None,
    auto_orient: bool = False,
    auto_arrange: bool = True,
    output_name: str = "ready_to_print.3mf",
    plate: str = "Textured PEI Plate",
) -> dict[str, Any]:
    """Slice geometry with exact installed profiles. Never sends a job to a printer."""
    cfg = load_config()
    if Path(output_name).name != output_name or "/" in output_name or "\\" in output_name or not output_name.endswith(".3mf"):
        raise ValueError("output_name must be a plain .3mf filename")
    if plate not in {"Textured PEI Plate", "Smooth PEI Plate", "Cool Plate", "Engineering Plate", "High Temp Plate"}:
        raise ValueError("Unsupported build plate; use its Bambu Studio name")
    model = Path(model_path).expanduser().resolve()
    mesh = load_mesh(model)
    if not mesh.is_watertight:
        raise ValueError("Repair the non-watertight mesh before slicing")
    outdir = Path(output_dir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    if model == outdir / output_name:
        raise ValueError("Output must not overwrite the input model")
    exe = find_bambu_executable(cfg.get("bambu_studio_path"))
    root = find_profile_root(exe, cfg.get("profile_root"))
    profiles = {k: flatten_profile(find_profile_file(root, k, n), root / k)
                for k, n in (("machine", machine_profile), ("process", process_profile), ("filament", filament_profile))}
    machine, process, filament = (profiles[k] for k in ("machine", "process", "filament"))
    for label, profile in (("process", process), ("filament", filament)):
        compatible = profile.get("compatible_printers", [])
        if compatible and machine.get("name", machine_profile) not in compatible:
            raise ValueError(f"{label} profile is incompatible with selected printer")
    process = safe_apply_process_overrides(process, process_overrides or {})
    nozzle = machine.get("nozzle_diameter", [0.4])
    nozzle = float(nozzle[0] if isinstance(nozzle, list) else nozzle)
    if float(process.get("layer_height", 0.2)) > 0.8 * nozzle:
        raise ValueError("Layer height exceeds 80% of the selected nozzle diameter")
    # Conservative initial bounding-box check; slicer checks arrangement and excluded regions.
    points = machine.get("printable_area", [])
    if points:
        xy = [tuple(map(float, v.split("x"))) for v in points]
        width = max(x for x,y in xy)-min(x for x,y in xy)
        depth = max(y for x,y in xy)-min(y for x,y in xy)
        height = float(machine.get("printable_height", 0))
        dims = mesh.extents
        if not auto_orient and (dims[0] > width or dims[1] > depth or (height and dims[2] > height)):
            raise ValueError("Model exceeds selected printer build volume; scaling is never automatic")
    output_3mf = outdir / output_name
    # Each run has a new directory: an earlier successful file cannot mask a failed export.
    with tempfile.TemporaryDirectory(prefix="bambu_autoprep_") as tmp:
        work = Path(tmp)
        mesh.export(work / "geometry.stl")  # strips imported project settings and custom G-code
        for name, data in (("machine", machine), ("process", process), ("filament", filament)):
            write_json(work / f"{name}.json", data)
        cmd = [str(exe), "--debug", "2", "--curr-bed-type", plate,
               "--load-settings", f"{work / 'machine.json'};{work / 'process.json'}",
               "--load-filaments", str(work / "filament.json")]
        if auto_orient:
            cmd += ["--orient", "1"]
        cmd += ["--arrange", "1" if auto_arrange else "0", "--slice", "0",
                "--outputdir", str(work), "--export-3mf", str(work / output_name),
                str(work / "geometry.stl")]
        proc = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True,
                              timeout=int(cfg.get("slice_timeout_seconds", 600)), shell=False)
        exported = work / output_name
        if proc.returncode != 0 or not exported.is_file():
            raise RuntimeError(f"Bambu Studio export failed ({proc.returncode}): {proc.stderr[-4000:]} {proc.stdout[-4000:]}")
        validate_sliced_3mf(exported)
        preview = work / "preview.png"
        preview_source = "embedded_slicer_preview"
        if extract_preview(exported, preview) is None:
            render_geometry_preview(mesh, preview)
            preview_source = "input_geometry_not_toolpaths"
        else:
            from PIL import Image
            with Image.open(preview) as im:
                im.verify()
        summary = {"machine_profile": machine.get("name", machine_profile),
                   "process_profile": process.get("name", process_profile),
                   "filament_profile": filament.get("name", filament_profile),
                   "plate": plate, "overrides": process_overrides or {},
                   "effective_process": {k:process[k] for k in sorted(SAFE_PROCESS_KEYS) if k in process},
                   "dimensions_mm": mesh.extents.tolist(), "auto_orient": auto_orient,
                   "auto_arrange": auto_arrange, "preview_source": preview_source,
                   "printer_started": False, "validated": "3MF ZIP, model, and nonempty sliced G-code"}
        write_json(work / "settings_summary.json", summary)
        from presentation import render_poster, create_guide
        render_poster(mesh, work / "print_image.png")
        create_guide(mesh, work / "Instruction_Manual.pdf", summary, output_name)
        # Commit artifacts only after every requested deliverable has been generated.
        for name in (output_name, "preview.png", "settings_summary.json", "print_image.png", "Instruction_Manual.pdf"):
            shutil.copy2(work / name, outdir / name)
    return {"ok": True, "three_mf": str(output_3mf), "preview_png": str(outdir / "preview.png"),
            "settings_summary": str(outdir / "settings_summary.json"),
            "instruction_pdf": str(outdir / "Instruction_Manual.pdf"), "print_image_png": str(outdir / "print_image.png"),
            "printer_started": False, "preview_source": preview_source}


@mcp.tool()
def prepare_print(model_path: str, output_dir: str, use: str = "general",
                  quality: str = "standard", machine_profile: Optional[str] = None,
                  filament_profile: Optional[str] = None, process_profile: Optional[str] = None) -> dict[str, Any]:
    """Choose conservative settings for supplied orientation and create the complete print package.

    Fine/draft require an explicit exact installed process profile. Functional layer orientation
    and support access remain review decisions; this tool never starts physical printing.
    """
    if use not in {"general", "decorative", "functional", "fit"} or quality not in {"standard", "fine", "draft"}:
        raise ValueError("Unknown intended use or quality")
    if quality != "standard" and not process_profile:
        raise ValueError("Fine/draft require an exact installed process profile from list_matching_profiles")
    cfg = load_config().get("defaults", {})
    analysis = analyze_model(model_path)
    x, y, z = analysis["dimensions_mm"]
    overrides = {"wall_loops": 4 if use == "functional" else 3,
                 "sparse_infill_density": "25%" if use == "functional" else "15%",
                 "enable_support": analysis["support_candidate_area_mm2"] > 1.0,
                 "brim_type": "outer_only" if z / max(min(x,y), 0.01) > 3 else "no_brim"}
    if overrides["brim_type"] == "outer_only":
        overrides["brim_width"] = 5
    return prepare_3mf(model_path, output_dir,
                       machine_profile or cfg.get("machine_profile", ""),
                       process_profile or cfg.get("process_profile_hint", ""),
                       filament_profile or cfg.get("filament_profile", ""),
                       process_overrides=overrides, auto_orient=False,
                       plate=cfg.get("plate", "Textured PEI Plate"))


if __name__ == "__main__":
    mcp.run()  # local stdio only; no unauthenticated HTTP listener or printer API
