# GTASceneSync — (v2.3.3)

# GTASceneSync — Description & How It Works

**Short description**
GTASceneSync is a Blender addon (San Andreas-focused) that helps export GTA-style IDE and IPL files from Blender scenes. It names instances by collection (strips `.dff`) or cleaned object names, lets you assign per-object IDE flags / TXD names, batch-assign TXDs, mark collision objects, then export IDE and (ASCII) IPL files ready for GTA San Andreas workflows.

### 🎯 Target Blender / Prerequisites

* **Blender 4.0+** (tested on 4.x; some backwards compatibility with earlier versions should work but not guaranteed).
* **No external Python libraries required** — built entirely with the Blender Python API.
* **Basic familiarity with Blender**:

  * Working with Collections (recommended workflow: group models by collection).
  * Selecting mesh objects.
* **Optional dependency**: *DragonFF* is required for some features, such as **To Collision**, to work correctly.
---

## Previews
[https://www.youtube.com/watch?v=mH0UEg7dVPs&feature=youtu.be](https://www.youtube.com/watch?v=mH0UEg7dVPs)

<img width="180" height="600" alt="Screenshot 2025-08-16 233755" src="https://github.com/user-attachments/assets/bc3cd366-06d1-4377-ad89-eae9b978e1d7" />


## Main features

* Export selected mesh objects to **IDE** (text) mapping (auto-assign model IDs).
* Export selected mesh objects to **ASCII IPL** (`inst` block — text format).
* Per-object IDE properties:

  * `texture_name` (TXD)
  * `ide_flag` (enumerated)
  * `render_distance`
* Batch assign TXD name to selected objects.
* Mark objects as **collision objects** using `To Collision` (safe `Object.dff.type = 'COL'` property).
* Utilities: batch rename, reset position, remove materials.
* Clean naming rules:

  * Collection names: `.dff` suffix stripped (case-insensitive)
  * Object names: numeric suffix `.1`, `.2` trimmed
* Scene-level `Start ID` setting to control the model id counter used when exporting.

---

## How it works (workflow)

1. **Prepare scene**

   * Put models into collections named after the model (optionally with a `.dff` suffix).
   * Select the mesh objects you want to export (selection order does not change ID assignment — IDs are assigned per unique collection/name).
2. **Set per-object metadata**

   * In the GTASceneSync panel (View3D → UI → GTASceneSync), select an object and set `TXD`, `Flag`, and `Draw Dist` using the per-object fields.
   * Use `Batch assign TXD` to set the same TXD for many objects quickly.
3. **Mark collision objects**

   * Select objects and press **To Collision**. The addon writes `obj.dff.type = 'COL'` (safe Blender property) to mark them as collision — used by downstream exporters / pipelines.
4. **Set Start ID**

   * Set `Start ID` in the panel if you want a custom model ID base. This value will prefill the export dialogs.
5. **Export IDE**

   * Click **Export IDE** → choose filename. The tool writes a text `.ide` file:

     ```
     objs
     <model_id>, <name>, <txd>, <draw_dist>, <flag>
     ...
     end
     ```
   * Unique names are assigned incremental model IDs starting from the Start ID.
6. **Export IPL (ASCII)**

   * Click **Export IPL** → choose filename. The tool writes an ASCII `inst` block (`inst ... end`) with object positions & rotations converted to GTA quaternion format (X/Y/Z negations to match game coordinate conventions). Binary IPL export was removed to avoid format issues.
7. **Use outputs**

   * Use the generated `.ide` and `.ipl` in your GTA SA pipeline / editors.

---

## Implementation notes & decisions

* **Name cleaning**: `clean_collection_name()` removes `.dff` (case-insensitive). `clean_name()` removes trailing `.N` numeric suffixes from object names.
* **Mapping**: Mapping uses the *collection name* where available, otherwise derived from the object name. That gives stable per-model IDs when many objects share a collection (recommended workflow).
* **Collision tagging**: Uses a registered `DFFProperties` pointer property (`Object.dff.type`) to stay API-correct and undo-friendly. A fallback plain custom property (`obj["dff_type"]`) is written if the pointer fails for some reason.
* **ASCII-only IPL**: The addon intentionally writes readable `inst` format to reduce accidental incompatibilities and to make debugging easier.
* **File writes**: IDE/IPL files written as UTF-8 text with safe try/except and user-facing error reporting.
* **Non-destructive**: Export is read-only to Blender data; marking collision only writes metadata to Blender objects (no mesh edits).

---

## Tips & best practices

* Group model meshes into a collection named `model.dff` (or `model`) so exports use the collection name automatically.
* Set `Start ID` to a value that won't collide with other model IDs you already have in your IDEs.
* Keep backups of original IDE/IPL files before integrating new entries.
* Use the **Batch assign TXD** to standardize textures quickly.
* Use `Batch Rename` to give consistent object names when needed.

---

## Known limitations / future ideas

* Binary IPL export intentionally removed for now
* IDE flags list currently minimal; you can expand `IDE_FLAGS` to include all SA flags with descriptions. but i will add them soon.
* Potential future additions: lod sorting and more sections of the ipl/ide file
