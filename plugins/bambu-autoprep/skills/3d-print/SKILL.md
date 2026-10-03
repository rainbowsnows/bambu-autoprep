---
name: 3d-print
description: Generate actual printable CAD or mesh geometry from descriptions or prepare existing STL, OBJ, 3MF and STEP models for FDM printing. Use for @3D Print and clear printable-object requests. Analyze geometry, choose installed Bambu Studio profiles, slice where supported and deliver model, 3MF, real preview, settings and guide without starting a printer.
---

# 3D Print

## Default: download, open, slice manually

Unless the user explicitly requests automatic Bambu slicing, deliver an **unsliced geometry 3MF** with STL, actual preview, settings recommendations and manual print guide. Bambu Studio or a Bambu MCP connection is not required for this export.

Use `generate_model` or task-specific geometry, then `prepare_unsliced_3mf`. Pass explicit hardware/material choices when provided. It writes geometry and a thumbnail, **not embedded Bambu profiles/process settings**. Tell the user to select installed profiles and apply the separate recommendations, slice and review, then manually start printing. Never describe this output as already sliced or settings already applied.

If local MCP is unavailable but the Work host provides Python/file execution, run the bundled script using the plugin's actual installed path:

`python <plugin-root>/mcp/unsliced.py --template ghost --output-dir <artifact-directory>`

For an existing model: `python <plugin-root>/mcp/unsliced.py --model <input-path> --output-dir <artifact-directory>`.

The host needs dependencies from `<plugin-root>/mcp/requirements.txt`; install them in the permitted host environment if needed. No Bambu executable or printer connection is used. For other objects export actual task-specific CAD/mesh geometry, then use the `--model` route. Link all five artifacts as downloads through the host's supported file delivery. If the host provides neither executable MCP nor Python/file execution, explain that generation/export cannot run on that surface; never fabricate a file or promise the repository alone enables execution.

## Geometry and optional automatic slicing

1. Understand the object and use. Apply explicit hardware/material/plate choices or configured defaults. Infer sensible decorative dimensions and state them. Ask only when scale, exact fit, rigidity, heat/outdoor use or material uncertainty materially affects the result.
2. Skip generation for uploads. For new objects use actual CAD or mesh geometry. `generate_model` builds a ghost, open desk cable holder or phone stand with millimetre parameters. Never misrepresent a template as another object.
3. For other geometric/functional objects, write and run task-specific parameterized code using available CadQuery, trimesh and manifold Boolean operations, then export STL/STEP. Use adequate walls (normally at least 1.2–2 mm for a 0.4 mm nozzle; more for structural parts). Do not execute arbitrary source through MCP.
4. For organic models use a connected tool returning actual meshes if available, or a suitable stylized procedural model. State fidelity limits. Never invent a generation service or substitute an image for geometry.
5. Run `analyze_model`. Inspect dimensions, watertightness, connected components, bed contact and overhang candidates. Normal/trivial-hole repair is conservative. Check design dimensions and sliced paths for walls, tiny details, bridges, fits and strength; analysis does not certify them. Fix reasonable issues in geometry code while preserving intended openings and separate parts.
6. Choose orientation for bed contact, visible surfaces, support removal and expected loads. Templates have flat bases. Rotate other models in CAD/mesh code if appropriate. Never scale fit-critical objects automatically.
7. For the default manual-slicing workflow, run `prepare_unsliced_3mf` without `health_check`. Only for requested automatic slicing run `health_check`; if unavailable, deliver the unsliced package and clearly state manual slicing is required. Do not fabricate sliced outputs.
8. Discover exact installed machine/process/filament names with `list_matching_profiles`. Verify hardware/nozzle/material compatibility. Missing profiles require updated local presets, not silent substitution. Honour user choices first.
9. Use `prepare_print` for conservative standard general/decorative/functional/fit choices or `prepare_3mf` for explicit geometry-specific choices. Fine/draft need a matching installed process. Decide or preserve vendor defaults for layer height, walls, top/bottom shells, infill amount/pattern, supports/style/threshold, brim, seam, thin-wall and overhang handling. Prefer walls before very high infill. Keep vendor temperature, acceleration, extrusion and machine G-code.
10. Check diagnostics and preview source. Export validation requires a valid model archive and nonempty sliced G-code. Embedded PNGs can be project thumbnails; fallback renders show input geometry, not supports/toolpaths. Label them. Inspect final placement, first layer, supports and fit in Bambu Studio before manual printing.
11. Deliver actual model file, unsliced 3MF by default (or sliced 3MF when explicitly requested and produced), actual preview PNG, important settings and PRINT_GUIDE.md together. Link usable files. Local MCP paths need host file transfer to become ChatGPT downloads; otherwise explain the output folder.

## Setup and boundaries

Root `mcp.json` declares local stdio on supported hosts. Install dependencies and Bambu Studio on that computer. Use `BAMBU_AUTOPREP_CONFIG` for private config if needed. Claim connection only after successful discovery and invocation.

STEP/STP requires optional CadQuery. Other formats need an available converter preserving units. Imported 3MF is reduced to geometry; original colours, settings, assembly metadata and custom G-code are removed.

The offline script needs host Python execution and dependencies, but no local Bambu connection. GitHub distributes the package; it does not deploy a Bambu service. Cloud Work/iPad needs a supported authenticated remote bridge and file delivery. Never insert placeholder endpoints or invented app IDs into active configuration.

Never send/start a physical print, disable protections, alter firmware, expose credentials or add printer-start APIs. Do not prepare harmful restricted designs. Never guarantee fit, strength, printability or absolute safety.
