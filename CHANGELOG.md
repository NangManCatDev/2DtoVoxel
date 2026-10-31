# Changelog

## Unreleased

### What the score can't see
- The score looks from one direction only, so a flat board or a floating roof can score well. Every build now also writes `_turn.png` (the model from four sides) and prints `depth:` (front-to-back depth ÷ width per object, `(thin)` under 0.5) and `loose:` (pieces touching nothing else of their object, with size and position). `m.loose_pieces()` lists them and `m.remove_loose()` deletes specks.
- `EXTRA_REFERENCES`: more pictures of the same object, each with its camera. Every build scores each one (its own `score <file>:` line and row in `_score.png`, plus the mean over all views), `score` puts them under `views`, and `fit-camera --ref N` finds the camera for picture N. `carve` lists its side and top drawings there itself.
- After the score, a build writes a full-resolution close-up of the area with the largest difference (`_zoom_<region>.png`). The model page has **Close-up** and **All sides** tabs.
- UI job prompts and the `/voxelize` skill tell Claude to check `_turn.png`, `(thin)` and `loose:`, and how to use more pictures.

### UI
- Delete a model from the sidebar: a bin icon on each model opens a confirmation that lists what will be moved and warns about other models that use it, MagicaVoxel edits and running jobs. Deleted models go to `output/_trash/<name>_<time>/` instead of being erased.
- **Trash** page: restore a deleted model (refused if the name is taken again) or delete it forever.
- New jobs preselect Opus. With "Default", a job stops right away if Claude Code's current model turns out to be Haiku, whose scripts were unusable.
- Cancelling a job and restoring a build use the page's own confirmation dialog.

### Models
- `m.damage(level)`: a broken variant of the model (chipped edges, holes, cracks, a caved-in top at level 3); pieces that lose their hold fall as rubble.

### Plants
- `m.tube()`: curved, tapering limbs with bark streaks. `m.foliage()`: voxel-art crowns made of clusters of small leaf clumps with a dark core, shaded light on top and outside. `m.tree()`: a whole tree (trunk, roots, limbs, crown) from your own lobes or a style (`round`, `column`, `cone`, `tiered`, `branched`, `spread`).
- `m.carve_to_reference()`: cuts voxels that land on the reference's background, to tidy organic outlines.
- `m.crown_depth()` (and `tree(lobes=..., view=VIEW)`): spreads lobes measured on a picture through the crown's depth, so crowns are round from every side instead of flat boards; the skill forbids filling an outline with a flat voxel layer and asks for a side/back check of organic models. Each cluster of touching lobes gets an upright ellipsoid with the measured outline, and lobes are copied along their own line of sight inside it, so the outline from the reference's side doesn't change.
- On a sheet of five tall trees (same measurements, only the leaf code replaced): IoU 0.847 → 0.869, ΔE 15.2 → 10.7 with `paint_reference`.
- The `/voxelize` skill tells Claude to use these for plants and to match a voxel-art reference's grain.

### High-resolution models
- Objects over 256 voxels per axis are saved as 256-voxel tiles in a named MagicaVoxel group, so big grids and big parts just work (MagicaVoxel shows scenes up to about 2048 per axis). `extrude` / `carve` results and `recolor` variants may exceed 256 too.
- `Model(..., res=N)` and `RES` in scripts: the same design in N× finer voxels, with smoother round shapes and roofs and finer textures. `voxtool build --res N` / `score --res N` override it for one run.
- `m.paint_reference(REFERENCE, VIEW)`: paints the voxels the reference shows with its own pixels (shading, stains, patterns), skipping colours too far from a voxel's own so materials don't bleed into each other; colours are reduced per material.
- `voxtool score --zoom <region | x0,y0,x1,y1>`: close-up of one area at the reference's full resolution (reference, build, difference).
- Faster previews for big models: past 150,000 visible faces a numpy z-buffer replaces drawing polygons one by one (a 1024 × 1024 terrain: 11 s → 3 s), and renders are capped at 3000 px.
- The 3D viewer handles grids over 255 (16-bit coordinates) and shows very large models coarser instead of freezing.
- The `/voxelize` skill has a high-resolution finishing step.

- README rewritten with [readme-craft](https://github.com/motiful/readme-craft): logo, why / features / when to use / quick start up front, and the details moved to `docs/` (how it works, model scripts, command line, troubleshooting), in English and Korean.
- Added `CONTRIBUTING.md`, `.github/repo-meta.yml` (About description and topics) and a logo.
- README shows a real generation run (scores per build, time, cost) with an animation of each build.
- `CLAUDE.md` is now in English.
- UI jobs on Windows: the voxtool permission rules now also cover Claude Code's PowerShell tool. Commands sent through it used to be denied (Claude retried them with Bash), and builds run through it were not snapshotted or counted toward the build limit.
- `SECURITY.md` and the README now say what the job allow-list does not do: the model script is Python that `build` runs with your rights, so the allow-list prevents mistakes but is not a sandbox.

## 0.2.0

### Quality of the build loop
- `voxtool score`: silhouette overlap (IoU), colour difference (CIE ΔE) and per-region misses against the reference, with a diff image. Every `build` of a script with a `REFERENCE` now scores itself and keeps a history (`<name>_scores.jsonl`).
- `voxtool fit-camera`: searches azimuth, elevation and field of view for the camera that best matches the reference.
- Perspective camera (`fov` in `VIEW`) next to the orthographic one; transparent and crisp (no supersampling) renders.
- `voxtool ref cutout`: background removal for references, including soft floor shadows, letterbox bars and see-through openings.

### Safety
- Builds back up a `.vox` that was saved from MagicaVoxel (`<name>_edited_<time>.vox`) before overwriting it.
- UI jobs may only edit their own model script and `output/`, run only voxtool commands and build only their own model.
- Every build in a UI job is snapshotted (script, comparison and score images, score); any version can be restored from the job page.
- Cost (`--max-budget-usd`) and build limits per job; "continue the previous conversation" for change requests.

### Input and output
- `voxtool extrude` (pixel art / images, flat or inflated) and `voxtool carve` (front/side/top silhouettes) convert without Claude; the result becomes `models/<name>.base.vox` plus a script that loads it (`Model.from_vox`, `m.paste_vox`).
- `voxtool sprites`: N-direction sprite sheet with a shared anchor and `manifest.json`.
- `voxtool export`: OBJ (+MTL + palette texture), PLY and GLB with greedy meshing; glowing colours become emissive materials.
- `voxtool recolor`: palette variants by named swaps or hue rotation.
- `m.part(name)`: kit sheets saved as separate MagicaVoxel objects.

### Project
- Installable package (`pip install -e .`, `voxtool` command); the UI moved to `voxtool/ui` and starts with `voxtool ui`.
- macOS/Linux: the UI picks `python3 -m voxtool` for Claude jobs, `2dtovoxel.sh` launcher, MagicaVoxel detection for `.app`.
- Test suite and CI (Windows + Ubuntu, Python 3.10 / 3.12).
- UI in English and Korean; README in both languages.

## 0.1.0

- `.vox` reader/writer, building DSL, preview renderer, reference study tools.
- `/voxelize` skill and the first model (`models/player_house.py`).
- Local web UI with live job logs, 3D preview and MagicaVoxel integration.
