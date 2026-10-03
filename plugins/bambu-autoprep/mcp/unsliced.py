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
                         printer: str | None = None, nozzle_mm: float = 0.4,
                         filament: str = "PLA", plate: str = "Textured PEI Plate") -> dict:
    """Create a geometry-only 3MF package; recommendations must be applied manually."""
    import json
    import shutil
    import tempfile
    from server import load_mesh, analyze_model, render_geometry_preview
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
        render_geometry_preview(mesh, preview)
        export_unsliced(mesh, work / output_name, preview)
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
        summary = {"status": "unsliced", "settings_embedded": False,
                   "requires_manual_slicing": True, "printer_started": False,
                   "requested_hardware": {"printer": printer, "nozzle_mm": nozzle_mm,
                                          "filament": filament, "plate": plate},
                   "recommended_settings": recommended, "analysis": analysis,
                   "preview_source": "actual_geometry_not_toolpaths",
                   "profile_note": "Select exact installed profiles in Bambu Studio; recommendations are not applied in this core 3MF."}
        (work / "settings_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        guide = ("# Print Guide — unsliced model\n\n"
                 "This 3MF contains actual geometry in millimetres and a thumbnail. It has no sliced toolpaths or embedded Bambu settings.\n\n"
                 f"1. Download {output_name} and open/import it in Bambu Studio as a model. If asked whether to import geometry, choose that option.\n"
                 "2. Select your actual printer, installed nozzle, filament and build plate using installed profiles.\n"
                 "3. Apply the recommendations in settings_summary.json; retain vendor temperature, machine and G-code defaults.\n"
                 "4. Check dimensions, plate fit, first-layer contact, orientation, wall thickness and support placement. Arrange on the plate.\n"
                 "5. Press Slice plate. Review the sliced preview and resolve any errors. Save the Bambu project if desired.\n"
                 "6. Start the print manually only after review. This plugin never starts a physical printer.\n\n"
                 "Support estimates may include bridges; inspect them. Fit, strength and tiny details need review.\n")
        (work / "PRINT_GUIDE.md").write_text(guide, encoding="utf-8")
        for name in (output_name, "printable_model.stl", "preview.png", "settings_summary.json", "PRINT_GUIDE.md"):
            shutil.copy2(work / name, outdir / name)
    return {"ok": True, "three_mf": str(outdir / output_name),
            "model_file": str(outdir / "printable_model.stl"), "preview_png": str(outdir / "preview.png"),
            "settings_summary": str(outdir / "settings_summary.json"), "print_guide": str(outdir / "PRINT_GUIDE.md"),
            "status": "unsliced", "settings_embedded": False, "requires_manual_slicing": True,
            "printer_started": False}


def main():
    """Host-execution fallback when local MCP isn't connected; never starts a server."""
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Create an unsliced 3MF download package")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--template", choices=["ghost", "cable-holder", "phone-stand"])
    source.add_argument("--model", help="STL/OBJ/3MF/STEP input")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parameters", default="{}", help="Template millimetre dimensions as JSON")
    parser.add_argument("--use", default="decorative", choices=["general", "decorative", "functional", "fit"])
    args = parser.parse_args()
    # Reuse library functions, without mcp.run(), Bambu discovery or subprocess slicing.
    from server import generate_model, prepare_unsliced_3mf
    model = args.model
    if args.template:
        model = generate_model(args.template, args.output_dir, json.loads(args.parameters))["model_file"]
    print(json.dumps(prepare_unsliced_3mf(model, args.output_dir, use=args.use), indent=2))


if __name__ == "__main__":
    main()
