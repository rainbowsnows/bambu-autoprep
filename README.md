# 3D Print

Generate actual printable geometry and prepare Bambu Studio print packages. The plugin's display name is **3D Print**; its repository and stable plugin ID remain **bambu-autoprep**.

## Install the marketplace

On a ChatGPT/Codex surface that supports GitHub marketplace imports, use this repository source:

https://github.com/rainbowsnows/bambu-autoprep

Select **3D Print** from the imported marketplace. Installing the marketplace distributes the plugin; it does not install Bambu Studio or deploy a slicing service.

Try:

`@3D Print Make a 3D model of a ghost.`

Existing models: `@3D Print Prepare this uploaded STL for printing.`

## What is implemented

- Deterministic, connected, watertight STL geometry for a ghost, desk cable holder and phone stand.
- A skill guiding task-specific CAD/mesh generation for other objects when the host provides suitable execution tools. No general neural text-to-3D service is bundled.
- STL, OBJ and 3MF analysis; optional STEP/STP conversion with CadQuery.
- Geometry previews rendered from the actual model, conservative repair and printability observations.
- Exact installed Bambu machine/process/filament profile discovery, bounded process overrides and local slicing.
- An unsliced geometry 3MF download package without Bambu Studio; optional sliced 3MF with connected local Bambu Studio.

The MCP tools never send a print job or start a physical printer. Review and start prints manually.

## Default workflow: download and slice yourself

Version 0.3.0 adds a core unsliced 3MF exporter. The normal workflow is:

**Describe/upload a model → receive unsliced 3MF + STL + actual preview + recommended settings + print guide → download on your computer → open/import in Bambu Studio → select installed profiles/apply recommendations → Slice plate → review → manually print.**

The geometry 3MF includes millimetre dimensions and a thumbnail. It does **not** embed Bambu profiles or automatically apply the recommended settings. Do not treat it as a preconfigured Bambu project or already sliced file.

No Bambu installation or Bambu MCP connection is needed to generate this unsliced package. The ChatGPT/Work host still needs Python/file execution or working local MCP tools, the bundled dependencies, and download delivery. The GitHub marketplace alone cannot provide those capabilities on an unsupported host.

On a Python-capable host:

`python -m pip install -r plugins/bambu-autoprep/mcp/requirements.txt`

`python plugins/bambu-autoprep/mcp/unsliced.py --template ghost --output-dir output`

Or for an uploaded file:

`python plugins/bambu-autoprep/mcp/unsliced.py --model input.stl --output-dir output`

The output folder contains model_unsliced.3mf, printable_model.stl, preview.png, settings_summary.json and PRINT_GUIDE.md.

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

Portable manifest/MCP schemas and marketplace paths validate. Seventeen automated tests pass, including real template meshes/renders and a **fixture slicer** testing package creation and failure handling. The fixture is not Bambu Studio.

Unsliced output is checked with ZIP/XML validation, independent trimesh re-import, preserved dimensions/closed volume, a real ghost CLI export, and guards against Bambu/subprocess calls. Real Bambu Studio opening/slicing, P2S installed-profile compatibility, installed ChatGPT invocation, optional STEP conversion and an end-to-end iPad workflow remain untested.

## Repository layout

- `.agents/plugins/marketplace.json`: marketplace catalog
- `plugins/bambu-autoprep/plugin.json`: plugin manifest and display metadata
- `plugins/bambu-autoprep/mcp.json`: local MCP configuration
- `plugins/bambu-autoprep/skills/bambu-autoprep/SKILL.md`: workflow instructions
- `plugins/bambu-autoprep/mcp/`: model generation and Bambu integration
- `tests/`, `schemas/`, `scripts/`: validation
