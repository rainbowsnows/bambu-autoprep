# Custom design specification

The agent interprets the user's description, chooses actual dimensions and writes geometry. This API receives geometry instructions, not a natural-language prompt and not executable Python. Never pretend the JSON engine automatically understands text.

Root: `{"version":1,"name":"Model name","shape":{...}}` or `{"version":1,"name":"Multipart model","parts":[{...},{...}]}`. All lengths are mm. `minimum_feature_mm` is optional declared design intent; it is not an analysis result. Use at least 1.2-2 mm walls for ordinary 0.4 mm FDM designs and more for load-bearing designs. Build appropriate dimensions into the actual shapes.

Each node has `type` plus these fields:

| Type | Fields | Coordinates |
| --- | --- | --- |
| box | size: [width,depth,height] | Centred at origin |
| sphere | radius | Centred at origin |
| ellipsoid | radii: [rx,ry,rz] | Centred at origin |
| cylinder | radius,height | Z axis, centred at origin |
| cone | radius,height | Base at Z=0 |
| torus | major_radius,minor_radius | Ring centred at origin in XY |
| extrude | points: [[x,y],...], optional holes: [ring,...], height | Sketch in XY, extrusion along +Z |
| revolve | profile: [[radius,z],...] | Close the profile to create the intended solid; rotates about Z |
| sweep | points, optional holes, path: [[x,y,z],...] | Closed profile swept along a non-self-intersecting path |
| text | text,size,height | Actual bold DejaVu Sans outlines in XY, extruded along +Z |
| organic | blobs: [{center:[x,y,z],radii:[rx,ry,rz]},...], optional resolution:24-96,level:0.05-0.9 | Smooth implicit ellipsoidal field; dimensions derive from the finished mesh |
| mesh | vertices:[[x,y,z],...],faces:[[i,j,k],...] | Closed, correctly indexed triangle geometry |
| union/difference/intersection | children:[node,node,...] | Difference keeps the first shape, subtracts all remaining children |

Every node can additionally have scale:[sx,sy,sz] (positive), rotate:[rx,ry,rz] (degrees around X/Y/Z), translate:[x,y,z]. They apply in that order after the operation. Use cylinders/spheres as cutting tools. Text alone has separate letters: fuse them to a plate for a connected printed sign. Connect stylized decorative appendages adequately; do not assume attractive shapes are strong.

Shape output moves down/up until minimum Z=0, preserving orientation and scale. `parts` instead lays separate part meshes on a bounded 250 mm plane with 8 mm gaps and each minimum Z=0. This is print layout, not assembly layout. It rejects an overflow instead of scaling. Prepare additional packages for more plates. Every resulting mesh must have finite coordinates, closed volume and reasonable complexity. Empty cuts, invalid sketches, unknown operations, excessive size/recursion, self-intersections that break volume and open meshes fail clearly.

## Custom pencil pot example

```json
{"version":1,"name":"Pencil pot","minimum_feature_mm":3,
 "shape":{"type":"difference","children":[
  {"type":"cylinder","radius":22,"height":60,"translate":[0,0,30]},
  {"type":"cylinder","radius":19,"height":60,"translate":[0,0,33]}
 ]}}
```

This has a 3 mm base and 3 mm radial wall. It is an open pot, not a drinking vessel. Build a different spec for a different requested object.

## Custom nameplate example

```json
{"version":1,"name":"Desk nameplate","minimum_feature_mm":2,
 "shape":{"type":"union","children":[
  {"type":"box","size":[70,25,3],"translate":[30,4,1.5]},
  {"type":"text","text":"HELLO","size":12,"height":1.2,"translate":[0,0,2.8]}
 ]}}
```

Choose text, font size and base to match the request. Measure finished extents: do not trust guessed text length.

## Full CAD fallback

If this DSL cannot express the object well, do not restrict the user's request to it. In supported host Python, install requirements-cad.txt, write actual task-specific CadQuery/mesh code and export the result:

```python
import cadquery as cq
from design import export_cadquery
# Example only: change this code to build the actual requested object.
part = cq.Workplane("XY").box(50,30,8).edges("|Z").fillet(3)
part = part.faces(">Z").workplane().hole(8)
files = export_cadquery(part, output_dir)
# Pass files['model_file'] into prepare_unsliced_3mf with real presentation/use steps.
```

The exported STL is checked for a closed volume; optional STEP retains editable CAD. For organic detail beyond procedural shapes, use an actually connected mesh generator or state the fidelity limit. No service/key is bundled. Preview actual geometry and prepare the completed mesh. Never fabricate a successful model or file.
