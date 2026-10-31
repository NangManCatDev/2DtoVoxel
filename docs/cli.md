# Command line and configuration

**English** | [한국어](cli.ko.md) · ← [Back to README](../README.md)

Run commands from the project folder. `voxtool` works after `pip install -e .`; otherwise use `py -m voxtool` (Windows) or `python3 -m voxtool` (macOS / Linux).

## Commands

| Command | What it does |
|---|---|
| `voxtool build models/<name>.py [--open] [--no-score] [--res N]` | Builds into `output/<name>/` (`.vox`, previews, comparison, score). Also prints `depth:` and, if there are any, `loose:` ([what the score can't see](how-it-works.md#what-the-score-cant-see)). `--open` opens MagicaVoxel; `--res` overrides the script's `RES` (finer voxels, same design) |
| `voxtool score models/<name>.py [--res N] [--zoom AREA]` | Scores against `REFERENCE` (and each of `EXTRA_REFERENCES`, under `views`) and prints JSON. `--zoom top-right` (a region of the score's 3×3 grid) or `--zoom x0,y0,x1,y1` (reference pixels) instead writes a close-up at the reference's full resolution → `_zoom_<area>.png` |
| `voxtool fit-camera models/<name>.py [--fovs 0,25,45] [--ref N]` | Finds the best `VIEW` and writes `_fit.png`. `--ref 1` fits the first picture in `EXTRA_REFERENCES` instead (→ `_fit_ref1.png`) |
| `voxtool angles models/<name>.py 30,20 42,15,30` | Renders `az,el[,fov]` cameras next to the reference → `_angles.png` |
| `voxtool render <file.vox> [--az 30 --el 30 --fov 0]` | Preview sheet for any `.vox`, including MagicaVoxel's own |
| `voxtool open <file.vox>` / `voxtool shot` | Opens a file in MagicaVoxel / captures its window (Windows) |
| `voxtool ref grid\|crop\|sample\|palette\|cutout <img>` | Reference study tools: pixel grid, zoomed crop, colour at points, dominant colours, cutout |
| `voxtool compare <a.png> <b.png> ...` | Side-by-side image |
| `voxtool extrude <img> --name N [--depth 4 --inflate]` | Image / pixel art → voxels, no Claude |
| `voxtool carve --front f [--side s --top t] --name N` | Silhouettes → voxels, no Claude |
| `voxtool sprites <script\|vox> [--dirs 8 --scale 4]` | Sprite sheet + `manifest.json` |
| `voxtool export <script\|vox> --format glb\|obj\|ply` | Mesh export |
| `voxtool recolor <script\|vox> --swap n=#hex \| --hue 30` | Palette variants |
| `voxtool ui [--port 8765] [--no-browser]` | Starts the web UI |
| `voxtool install-skill [--dest ~/.claude/skills]` | Makes `/voxelize` available in every project |

## Outputs

Everything generated goes to `output/<name>/` and can be rebuilt at any time (the folder is git-ignored):

| File / folder | Content |
|---|---|
| `<name>.vox` | The model |
| `<name>_iso.png`, `_sheet.png` | 3/4 preview, all views |
| `<name>_turn.png` | The model from four sides, a quarter turn apart, starting at the reference's side |
| `<name>_compare.png`, `_score.png`, `_scores.jsonl` | Reference comparison, diff image (one row per reference), score history |
| `<name>_angles.png`, `_fit.png`, `_fit_ref<N>.png` | Camera tries, camera fit |
| `<name>_zoom_<area>.png` | Close-up from `score --zoom`, or of the area with the largest difference after a build |
| `<name>_edited_<time>.vox` | Backup of a file you had saved from MagicaVoxel |
| `sprites/`, `export/`, `variants/` | Sprite sheet + manifest, meshes, palette variants |

UI job logs and per-build snapshots live in `output/_jobs/<id>/`.

## Configuration

| Setting | How |
|---|---|
| Claude Code CLI location | Environment variable `CLAUDE_CLI` = full path to the `claude` executable |
| MagicaVoxel location | Environment variable `MAGICAVOXEL_EXE` = full path to `MagicaVoxel.exe` (or the `.app` on macOS) |
| Port | `voxtool ui --port 9000` (falls back to the next free port) |
| Don't open a browser | `voxtool ui --no-browser` |
| UI language | Picker in the top-right corner; defaults to your browser's language |
| Per-job limits | "Max cost (USD)" and "Max builds" fields in the UI |

The UI finds `claude` on your `PATH`, or the copy bundled with the Claude Code extension for VS Code (also VS Code Insiders and Cursor). MagicaVoxel is detected in common places: a `MagicaVoxel*` folder on the Desktop, in Downloads, in your home folder, in `C:\Program Files` or under `C:\`; `/Applications` on macOS.
