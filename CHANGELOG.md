# Changelog

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
