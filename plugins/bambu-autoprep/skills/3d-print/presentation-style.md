# Required presentation

The owner's references define the visual style, not the dimensions or instructions
for another object. Use the bundled renderer so every job uses the same palette,
typography and layout. Never replace real model views with unrelated concept art.

## PNG poster

- 1800 × 1280 px, cream background `#F7F9F6`.
- Upper-left bold uppercase dark-green title `#153F37`, muted subtitle `#58716B`.
- Two large teal `#61AD99` orthographic views, clean hidden surfaces, no axes/grid.
- Bold view labels and concise captions below each view.
- Thin pale divider, measured X × Y × Z dimensions, illustration footer.
- Front/reverse views are the default. Use accurate assembled/open/usage views only
  if actual part geometry and verified placement exist. Label nonprinted props;
  never silently add them to the print files. A second angle is not an assembly state.

## PDF instructions only

`compact` follows the pocket guide: normally two cream A4 pages. Page 1 has an
uppercase title, rounded three-dimension strip, actual CAD view on the left,
saved-settings table on the right, numbered print steps and pale green note.
Page 2 has a CAD view and purpose/requirements/size columns, finishing instructions,
numbered assembly/use steps and care note.

`editorial` follows the lift-out manual: normally three white A4 pages. Overview
with a sentence-case hero, warm beige note and two CAD views; a print page with
views, a full-width ruled settings table and numbered steps; then a use page
with views, numbered green circles and a warm note. Extra pages are allowed for
long instructions. Every page has a divider and page count. Fonts are embedded.

Deliver one `Instruction_Manual.pdf`. Do not generate a second `.md`, `.txt` or
chat text guide. A concise settings summary is still required. The guide must
distinguish unsliced, sliced and geometry-only files and instruct manual review.
No physical testing, print times or material estimates may be invented.

## Metadata

Pass an object to the `presentation` parameter on either preparation workflow:

```json
{
  "title": "Pencil pot",
  "subtitle": "A simple home for pencils on your desk.",
  "overview": "An open-top pot with a flat solid base.",
  "requirements": "One printed pot. No hardware or assembly.",
  "use_heading": "Using your pencil pot",
  "use_steps": [
    {"heading": "Place on a flat desk", "body": "Set the pot upright and check that it sits steadily."},
    {"heading": "Add your pencils", "body": "Place pencils inside the open top. Avoid overfilling."}
  ],
  "use_note": "For dry indoor storage. Keep PLA away from hot surfaces.",
  "guide_style": "compact"
}
```

Write fresh content for the actual object. Limits: title 160 characters; subtitle
240; overview 600; requirements 350; use_heading 100; use_note 500. At most four
use steps, each with heading up to 100 and body up to 500 characters. Plain-string
steps remain supported. Choose concise wording; the layout wraps and paginates.
Known purpose should yield specific use/assembly instructions, not generic filler.

For a custom diagram/layout beyond the automatic renderer, keep the same visual
contract, actual geometry and measured settings. Inspect the final PNG and every
PDF page before returning them. Pixel-identical content is not appropriate when
the printable object, parts and instructions differ from the reference examples.
