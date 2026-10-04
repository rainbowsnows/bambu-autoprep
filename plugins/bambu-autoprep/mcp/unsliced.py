"""Core 3MF geometry export. No Bambu installation, profiles or printer access."""
from pathlib import Path
import math
import zipfile
from xml.etree import ElementTree as ET

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"


def xml_bytes(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def export_unsliced(mesh, destination: Path, preview: Path | None = None):
    """Write a millimetre core 3MF with the supplied orientation and no toolpaths."""
    if not mesh.is_watertight or not mesh.is_volume:
        raise ValueError("Unsliced export requires a closed, consistently wound volume")
    if not all(math.isfinite(float(v)) for row in mesh.vertices for v in row):
        raise ValueError("Mesh coordinates must be finite")
    model = ET.Element("model", {"xmlns": CORE, "unit": "millimeter",
                                "{http://www.w3.org/XML/1998/namespace}lang": "en-US"})
    ET.SubElement(model, "metadata", {"name": "Application"}).text = "3D Print"
    resources = ET.SubElement(model, "resources")
    obj = ET.SubElement(resources, "object", {"id": "1", "type": "model"})
    element = ET.SubElement(obj, "mesh")
    vertices = ET.SubElement(element, "vertices")
    for row in mesh.vertices:
        ET.SubElement(vertices, "vertex", dict(zip(("x", "y", "z"),
                      (format(float(v), ".17g") for v in row))))
    triangles = ET.SubElement(element, "triangles")
    for row in mesh.faces:
        ET.SubElement(triangles, "triangle", dict(zip(("v1", "v2", "v3"),
                      (str(int(v)) for v in row))))
    ET.SubElement(ET.SubElement(model, "build"), "item", {"objectid": "1"})
    types = ET.Element("Types", {"xmlns": TYPES})
    for ext, content in [("rels", "application/vnd.openxmlformats-package.relationships+xml"),
                         ("model", "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"),
                         ("png", "image/png")]:
        ET.SubElement(types, "Default", {"Extension": ext, "ContentType": content})
    relationships = ET.Element("Relationships", {"xmlns": REL})
    ET.SubElement(relationships, "Relationship", {
        "Id": "rel0", "Target": "/3D/3dmodel.model",
        "Type": "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"})
    if preview:
        ET.SubElement(relationships, "Relationship", {
            "Id": "rel1", "Target": "/Metadata/thumbnail.png",
            "Type": "http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"})
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", xml_bytes(types))
        archive.writestr("_rels/.rels", xml_bytes(relationships))
        archive.writestr("3D/3dmodel.model", xml_bytes(model))
        if preview:
            archive.write(preview, "Metadata/thumbnail.png")


def prepare_unsliced_3mf(model_path: str, output_dir: str, use: str = "general",
                         output_name: str = "model_unsliced.3mf",
                         printer: str | None = None, nozzle_mm: float | None = None,
                         filament: str | None = None, plate: str | None = None,
                         embed_settings: bool = True, project_template_path: str | None = None,
                         presentation: dict | None = None, process_overrides: dict | None = None) -> dict:
    """Create an unsliced Bambu project with applied settings, or optional geometry-only export."""
    from presentation import metadata, render_poster, create_guide
    presentation = metadata(presentation)
    import json
    import shutil
    import tempfile
    from server import load_mesh, analyze_model, load_config, safe_apply_process_overrides
    config = load_config()
    defaults = config.get("unsliced_defaults", config.get("defaults", {}))
    printer = printer or defaults.get("printer") or defaults.get("machine_profile")
    nozzle_mm = nozzle_mm if nozzle_mm is not None else float(defaults.get("nozzle_mm", 0.4))
    filament = filament or defaults.get("filament") or defaults.get("filament_profile") or "PLA"
    plate = plate or defaults.get("plate", "Textured PEI Plate")
    project_template_path = project_template_path or defaults.get("project_template_path")
    safe_apply_process_overrides({}, process_overrides or {})
    if use not in {"general", "decorative", "functional", "fit"}:
        raise ValueError("Unknown intended use")
    if not math.isfinite(nozzle_mm) or not 0.2 <= nozzle_mm <= 1.0:
        raise ValueError("Nozzle must be between 0.2 and 1.0 mm")
    if Path(output_name).name != output_name or "/" in output_name or "\\" in output_name or not output_name.endswith(".3mf"):
        raise ValueError("output_name must be a plain .3mf filename")
    model = Path(model_path).expanduser().resolve()
    mesh = load_mesh(model)
    if not mesh.is_watertight or not mesh.is_volume:
        raise ValueError("Repair the geometry to a closed volume before exporting")
    mesh.apply_translation([0, 0, -mesh.bounds[0, 2]])
    outdir = Path(output_dir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    if model in {outdir / output_name, outdir / "printable_model.stl"}:
        raise ValueError("Output must not overwrite the input model")
    with tempfile.TemporaryDirectory(prefix="3d_print_unsliced_") as tmp:
        work = Path(tmp)
        stl = work / "printable_model.stl"
        mesh.export(stl)
        analysis = analyze_model(str(stl))
        preview = work / "preview.png"
        render_poster(mesh, preview, presentation)
        x, y, z = analysis["dimensions_mm"]
        recommended = {
            "layer_height": round(min(0.2, nozzle_mm * 0.5), 3),
            "wall_loops": 4 if use == "functional" else 3,
            "top_shell_layers": 5, "bottom_shell_layers": 4,
            "sparse_infill_density": "25%" if use == "functional" else "15%",
            "sparse_infill_pattern": "gyroid",
            "enable_support": analysis["support_candidate_area_mm2"] > 1,
            "brim_type": "outer_only" if z / max(min(x, y), 0.01) > 3 else "no_brim",
            "seam_position": "aligned"}
        if recommended["brim_type"] == "outer_only":
            recommended["brim_width"] = 5
        recommended.update(process_overrides or {})
        if float(recommended["layer_height"]) > .8 * nozzle_mm:
            raise ValueError("Layer height exceeds 80% of the selected nozzle diameter")
        embedded = {}
        if embed_settings:
            from bambu_project import export_bambu_project
            embedded = export_bambu_project(mesh, work / output_name, preview, recommended,
                printer, nozzle_mm, filament, plate, project_template_path)
        else:
            export_unsliced(mesh, work / output_name, preview)
        summary = {"status": "unsliced", "settings_embedded": embed_settings,
                   "requires_manual_slicing": True, "printer_started": False,
                   "requested_hardware": {"printer": printer, "nozzle_mm": nozzle_mm,
                                          "filament": filament, "plate": plate},
                   "recommended_settings": recommended, "embedded_profiles": embedded, "analysis": analysis,
                   "effective_process": embedded.get("effective_settings", {}),
                   "settings_decisions": {"orientation": "Supplied orientation, placed on the bed; inspect before slicing",
                       "quality": "Conservative layer height unless explicitly overridden",
                       "strength": "Walls and infill chosen from intended use: " + use,
                       "supports": "Overhang candidates in the actual geometry; inspect bridges and removal access",
                       "advanced_settings": "Unchanged vendor defaults for all settings outside the bounded process overrides"},
                   "preview_source": "actual_geometry_not_toolpaths",
                   "profile_note": "Settings are saved inside the Bambu project; open as a project to load them." if embed_settings else "Geometry only: apply recommendations manually."}
        (work / "settings_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        create_guide(mesh, work / "Instruction_Manual.pdf", summary, output_name, presentation)
        for name in (output_name, "printable_model.stl", "preview.png", "settings_summary.json", "Instruction_Manual.pdf"):
            shutil.copy2(work / name, outdir / name)
    return {"ok": True, "three_mf": str(outdir / output_name),
            "model_file": str(outdir / "printable_model.stl"), "preview_png": str(outdir / "preview.png"),
            "settings_summary": str(outdir / "settings_summary.json"),
            "instruction_pdf": str(outdir / "Instruction_Manual.pdf"),
            "status": "unsliced", "settings_embedded": embed_settings, "requires_manual_slicing": True,
            "printer_started": False}


def main():
    """Host-execution fallback when local MCP isn't connected; never starts a server."""
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Create an unsliced 3MF download package")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--template", choices=["ghost", "cable-holder", "phone-stand"])
    source.add_argument("--model", help="STL/OBJ/3MF/STEP input")
    source.add_argument("--design", help="Custom design JSON file; not limited to named templates")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parameters", default="{}", help="Template millimetre dimensions as JSON")
    parser.add_argument("--use", default="decorative", choices=["general", "decorative", "functional", "fit"])
    parser.add_argument("--geometry-only", action="store_true", help="Export geometry without Bambu settings")
    parser.add_argument("--project-template", help="Matching unsliced single-object Bambu project")
    parser.add_argument("--printer")
    parser.add_argument("--nozzle-mm", type=float)
    parser.add_argument("--filament")
    parser.add_argument("--plate")
    parser.add_argument("--process-overrides", default="{}", help="JSON of bounded safe process settings")
    parser.add_argument("--presentation", default="{}", help="JSON: title, subtitle, overview, requirements, use_steps, use_note, guide_style")
    args = parser.parse_args()
    # Reuse library functions, without mcp.run(), Bambu discovery or subprocess slicing.
    from server import generate_model, prepare_unsliced_3mf
    model = args.model
    presentation = json.loads(args.presentation)
    if args.design:
        from design import generate_custom_model
        path = Path(args.design)
        if path.stat().st_size > 2_000_000:
            raise ValueError("Design JSON exceeds size limit")
        design = json.loads(path.read_text())
        presentation.setdefault("title", design.get("name", "Custom model"))
        model = generate_custom_model(design, args.output_dir, presentation)["model_file"]
    if args.template:
        presentation.setdefault("title", args.template.replace("-", " ").title())
        uses = {"ghost": "Place the finished ghost on a stable flat surface as a decoration.", "cable-holder": "Place the holder on a flat desk and lay a suitably sized cable in its open groove. This is not a snap clip.", "phone-stand": "Place the stand on a stable desk, seat the phone behind the front lip and check balance before letting go."}
        presentation.setdefault("use_steps", [uses[args.template]])
        model = generate_model(args.template, args.output_dir, json.loads(args.parameters))["model_file"]
    print(json.dumps(prepare_unsliced_3mf(model, args.output_dir, use=args.use, embed_settings=not args.geometry_only, project_template_path=args.project_template, printer=args.printer, nozzle_mm=args.nozzle_mm, filament=args.filament, plate=args.plate, presentation=presentation, process_overrides=json.loads(args.process_overrides)), indent=2))


if __name__ == "__main__":
    main()
