# 3D Print

Generate actual printable geometry and prepare Bambu Studio print packages. The plugin's display name is **3D Print**; its repository and stable plugin ID remain **bambu-autoprep**.

## Install the marketplace

On a ChatGPT/Codex surface that supports GitHub marketplace imports, use this repository source:

https://github.com/rainbowsnows/bambu-autoprep

If your Plugins screen offers **Upload plugin archive** instead of marketplace imports, generate the personal upload ZIP with:

`python scripts/package_plugin.py`

Then upload `3D-Print-0.6.0.zip` through that option. This ZIP contains the skills and Python tools, without an active local stdio MCP configuration. It uses supported Work host Python/file execution for unsliced export. The GitHub source retains the local Bambu MCP configuration. To package that configuration for a compatible local host, use `python scripts/package_plugin.py --local-mcp`.

Archive-installed plugins are a snapshot: a later GitHub commit does not update them automatically; upload an updated archive through the host's supported update flow.

Select **3D Print** from the imported marketplace. Installing the marketplace distributes the plugin; it does not install Bambu Studio or deploy a slicing service.

Try:

`@3D Print Make a 3D model of a ghost.`

Existing models: `@3D Print Prepare this uploaded STL for printing.`

## What is implemented

- General custom CAD/mesh generation guided by ChatGPT, with a bounded JSON design engine and optional full CadQuery CAD. Ghost, cable holder and phone stand remain examples, not the object limit.
- A skill guiding task-specific CAD/mesh generation for other objects when the host provides suitable execution tools. No general neural text-to-3D service is bundled.
- STL, OBJ and 3MF analysis; optional STEP/STP conversion with CadQuery.
- Geometry previews rendered from the actual model, conservative repair and printability observations.
- Exact installed Bambu machine/process/filament profile discovery, bounded process overrides and local slicing.
- An unsliced Bambu project with saved settings without Bambu Studio; optional sliced 3MF with connected local Bambu Studio.

The MCP tools never send a print job or start a physical printer. Review and start prints manually.

## Default workflow: download and slice yourself

Version 0.5.0 saves the selected settings inside an unsliced Bambu project. The normal workflow is:

**Describe/upload a model → receive unsliced 3MF + STL + actual preview + recommended settings + print guide → download on your computer → open as a PROJECT in Bambu Studio → review saved hardware/settings → Slice plate → review → manually print.**

The default Bambu project contains actual geometry, selected print settings, vendor machine/material defaults and a thumbnail. It is still **unsliced**. Open as a **project** to load settings; importing geometry alone discards them.

The bundled reference was generated with official Bambu Studio 02.08.02.61 using P2S, 0.4 mm nozzle, Bambu PLA Basic and Textured PEI Plate. Other printer/nozzle/material choices require a matching unsliced single-object project template (`--project-template` or `project_template_path`); unsupported hardware is rejected rather than substituted. The optional `--geometry-only` mode retains the earlier geometry-only route with separate recommendations.

Bambu Studio here successfully reopened/exported the ghost project with every chosen setting retained and sliced it without a physical printer connection. Your exact installed Bambu version, UI flow and ChatGPT account invocation are still untested.

No Bambu installation or Bambu MCP connection is needed to generate this unsliced package. The ChatGPT/Work host still needs Python/file execution or working local MCP tools, the bundled dependencies, and download delivery. The GitHub marketplace alone cannot provide those capabilities on an unsupported host.

On a Python-capable host:

`python -m pip install -r plugins/bambu-autoprep/mcp/requirements.txt`

`python plugins/bambu-autoprep/mcp/unsliced.py --template ghost --output-dir output`

Or for an uploaded file:

`python plugins/bambu-autoprep/mcp/unsliced.py --model input.stl --output-dir output`

The output folder contains model_unsliced.3mf, printable_model.stl, preview.png, settings_summary.json and Instruction_Manual.pdf.

## Optional automatic Bambu slicing: one-time computer setup

Bambu Studio and Python 3.10 or newer must be installed on the computer running the MCP server.

1. Clone/download this repository.
2. Install dependencies from the repository folder:

   `python -m pip install -r plugins/bambu-autoprep/mcp/requirements.txt`

3. Copy `plugins/bambu-autoprep/mcp/config.example.json` to `plugins/bambu-autoprep/mcp/config.json`.
4. Set the Bambu executable and BBL profile folder paths if automatic discovery fails.
5. Set defaults using the **exact profiles installed with your Bambu Studio**. Example profile names are placeholders to verify, not guarantees that those profiles exist. The profile folder contains machine, process and filament subfolders.
6. On a host supporting plugin local stdio MCP, enable the included `plugins/bambu-autoprep/mcp.json`. Ensure `python` resolves to the interpreter with these dependencies. For manual MCP configuration use command `python` with the absolute path to `plugins/bambu-autoprep/mcp/server.py`.
7. Invoke `health_check`, then `list_matching_profiles` to verify discovery before slicing.

Private configuration can live outside the repository using the `BAMBU_AUTOPREP_CONFIG` environment variable. Do not commit credentials or personal configuration.

STEP/STP additionally needs `python -m pip install cadquery`. This optional route has not been tested here.

**iPad/cloud:** unsliced export can run in a supported Work host with Python/file execution and dependencies, without connecting your computer. Automatic Bambu slicing still requires a supported local host or authenticated remote bridge; this repository does not deploy that bridge.

## Settings and limitations

Explicit printer, nozzle, filament and plate choices take priority over configured defaults. The standard automatic path selects walls, infill, supports and brim based on intended use and geometry; other settings retain the selected vendor profile unless explicitly overridden. More detailed orientation, fit and geometry decisions are guided by the skill and require host tools.

Analysis does not certify minimum wall thickness, strength, fit or every tiny feature. Imported 3MF is converted to geometry, removing original colours, project settings and custom G-code. Units must be checked for STL/OBJ.

Previews may be embedded project thumbnails or actual input-geometry renders. A geometry render does not show sliced supports or toolpaths.

## Validation

`python -m pip install -r requirements-dev.txt`

`python scripts/validate_plugin.py`

`python -m pytest -q`

Portable manifest/MCP schemas and marketplace paths validate. Automated geometry, native project and settings-preservation tests pass, including real template meshes/renders and a **fixture slicer** testing package creation and failure handling. The fixture is not Bambu Studio.

Unsliced output is checked with ZIP/XML validation, independent trimesh re-import, preserved dimensions/closed volume, a real ghost CLI export, and guards against Bambu/subprocess calls. Official Bambu Studio 02.08.02.61 reopening/settings re-export and slicing were tested on the default P2S/0.4/PLA ghost. Installed ChatGPT invocation, your computer UI/version, other hardware templates and an end-to-end iPad workflow remain untested. Custom design operations, multipart layout, real text holes, organic closed meshes, and CadQuery STL/STEP export/import were tested locally in 0.6.0.

## Repository layout

- `.agents/plugins/marketplace.json`: marketplace catalog
- `plugins/bambu-autoprep/plugin.json`: plugin manifest and display metadata
- `plugins/bambu-autoprep/mcp.json`: local MCP configuration
- `plugins/bambu-autoprep/skills/3d-print/SKILL.md`: workflow instructions
- `plugins/bambu-autoprep/mcp/`: model generation and Bambu integration
- `tests/`, `schemas/`, `scripts/`: validation

Vendor template provenance and license: `plugins/bambu-autoprep/assets/README.md`.

## Preview and guide style (0.5.0)

Actual geometry is rendered in orthographic teal CAD views on a cream background, with a dark green uppercase title, two labelled views, real dimensions and an honest illustration footer. No unrelated concept image or invented assembly state is used. Both sides show the same geometry; the script does not infer removed lids or usage props from a single mesh.

The default two-page PDF follows the compact print-and-use guide style: dimension strip, actual-model illustration, settings table, numbered print steps, finishing/use steps and pale green notes. `guide_style: "editorial"` uses the roomier manual palette with white paper and warm note boxes. Instructions are delivered only as the illustrated PDF; no extra Markdown or text guide is generated.

Supply `--presentation '{"title":"Ghost","subtitle":"A small desk decoration","use_steps":["Place on a stable shelf."],"guide_style":"compact"}'` or the MCP `presentation` object for task-specific text. Allowed fields: title, subtitle, up to four use_steps, use_note, guide_style (compact/editorial). Write use steps from the actual design, never fabricate fit, assembly, extra parts, slicing estimates or physical testing. Long instructions that exceed the layout are rejected instead of clipped. Other objects can use this presentation pipeline after actual geometry generation.

Output additionally includes `Instruction_Manual.pdf`. Automatic-slicing packages also include `print_image.png` separately from the slicer preview, preserving the distinction between geometry and toolpaths. Exact pixel identity with reference images is not promised: the object, dimensions, view and instructions change with the actual model.

## Custom objects (0.6.0)

ChatGPT translates descriptions into task-specific CAD/mesh geometry rather than choosing only three preset models. The bundled `generate_custom_model` MCP tool supports custom Boolean shapes, polygon extrusions with holes, revolved profiles, swept profiles, extruded text, custom triangle meshes and smooth organic blobs. Optional full CadQuery supports task-specific Python CAD, including fillets, shells and lofts. All generation must run on a supported execution host; installing a ZIP alone does not provide compute or an external generation service.

Read `skills/3d-print/design-spec.md` for the JSON schema examples. Run `python plugins/bambu-autoprep/mcp/unsliced.py --design design.json --output-dir output --use functional --presentation '{"title":"My custom model","use_steps":["Use the actual printed part as described."]}'`. No image-generation substitute is used. `--model` accepts geometry created with full CAD or another actually connected 3D tool. For full CAD/STEP install `python -m pip install -r plugins/bambu-autoprep/mcp/requirements-cad.txt` and call `design.export_cadquery` from a host geometry script.

This is broader model generation, not a guarantee to produce any imaginable geometry accurately. Complex organic likenesses may require an external mesh generator (not bundled); exact fits need dimensions; large multipart models need multiple packages. Declared minimum features are design intent, not measured certification. User-account invocation, external generators, other hardware and physical fit/printing remain untested. Existing printer/material/template limits remain unchanged.
