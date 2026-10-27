# Changelog

## Unreleased

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
