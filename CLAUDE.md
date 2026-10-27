# 2DtoVoxel

A project where Claude looks at a reference image (`reference/`) and builds a MagicaVoxel model (`.vox`) from it.
Don't drive the MagicaVoxel GUI. **Write a model build script (`models/<name>.py`) → generate the `.vox` directly →
compare with the reference using our own preview renders and measured scores, and iterate → open it in MagicaVoxel.**

When a new reference comes in, follow the `/voxelize <image path>` skill (`.claude/skills/voxelize/SKILL.md`).

## Environment
- Python 3.10+ (numpy, Pillow, scipy). On Windows run `py -m voxtool ...`; on macOS/Linux `python3 -m voxtool`.
  After `pip install -e .` there is also a `voxtool` command. Run every command from the workspace (this folder).
- MagicaVoxel is found automatically (Desktop / Downloads / home / Program Files, `/Applications` on macOS);
  override with `MAGICAVOXEL_EXE`.
- Tests: `py -m pytest -q` (tests/ really runs the CLI and the server in temporary workspaces). CI: `.github/workflows/ci.yml`.

## Layout
- `voxtool/vox_io.py` — .vox read/write (SIZE/XYZI/RGBA/MATL + scene graph). Max 256 per axis per object.
  `backup_if_edited()`: if the file was saved by MagicaVoxel (it has chunks our writer never writes, like rOBJ/rCAM),
  copy it before overwriting.
- `voxtool/model.py` — building DSL (`Model`, `Palette`). Primitives, architecture, organic helpers, `part()`,
  `from_vox()/paste_vox()`.
- `voxtool/render.py` — `Camera` (orthographic / perspective `fov`), `render_iso` (transparent and crisp modes),
  sheet with 5 orthographic views.
- `voxtool/reftools.py` — reference study tools (grid, crop, colour samples, palette) + `cutout()` background removal.
- `voxtool/score.py` — `score_model` (silhouette IoU, colour ΔE, missing/extra per 3×3 region, diff image), `fit_camera`.
- `voxtool/convert.py` — conversions without Claude: `extrude` (pixel-art slab / inflate), `carve` (multi-view silhouette
  intersection).
- `voxtool/export.py` — greedy meshing → OBJ/PLY/GLB, sprite sheet + manifest.json, palette variants.
- `voxtool/__main__.py` — the whole CLI. `voxtool/ui/` — web UI (`voxtool ui`, `py -m ui`, `2DtoVoxel.bat`, `2dtovoxel.sh`).
- `models/<name>.py` — one build script per model. `NAME`, `REFERENCE`, `VIEW` (+`fov`); optional `SCORE_VIEW`, `CUTOUT`.
  Conversion results are `models/<name>.base.vox` (source data, committed) + a script that loads it.
- `output/<name>/` — `.vox`, `_iso/_sheet/_compare/_score/_fit.png`, `_scores.jsonl`, `sprites/ export/ variants/`
  (generated, can be rebuilt any time, git-ignored). `output/_jobs/<id>/` — UI job logs and per-build snapshots (`iter/`).

## Permissions of UI jobs (important)
When the UI runs Claude it uses `--permission-mode dontAsk` and allows only `allowed_tools(name)` from
`voxtool/ui/jobs.py`: file edits only in `models/<name>.py` and `output/**`; Bash only
`<VT> build|angles|score|fit-camera models/<name>.py`, `<VT> ref|render|compare` and `ls` (no `-c` code).
`<VT>` is picked per OS by `voxtool_command()` (Windows `py -m voxtool`, otherwise `python3 -m voxtool`) — the prompt
and the permission rules must contain the same string.
So the skill/CLI workflow must work with voxtool commands only (no `cd`, `&&` or `-c`), and features the library lacks
go into the model script as helpers. (This lockdown exists because a UI job once edited the shared `voxtool/model.py`
and rebuilt another model, overwriting the user's MagicaVoxel edits.)
- Every time a job builds its own model (the tool result of `build models/<name>.py`), the script, comparison/score
  images and score are snapshotted to `output/_jobs/<id>/iter/`. Any version can be restored from the job page
  (`JobManager.restore`).
- Per-job cost cap (`--max-budget-usd`), build cap (in the prompt + forced stop at cap+2), continue the previous
  session (`--resume`).

## Languages
- The UI is English/Korean. Screen text lives in `voxtool/ui/static/i18n.js` (same keys in both languages), server
  errors in `UserError(key)` from `voxtool/ui/i18n.py`, Claude prompts in `PROMPTS[lang]` in `jobs.py`. Always add
  new text in both languages. Job log entries are stored as a `key` instead of a sentence, so switching the UI
  language also re-words past logs.
- README is `README.md` (English) and `README.ko.md` (Korean), structured with readme-craft: a short storefront
  (logo, one-liner, badges, why, features, when to use, quick start, install, usage) with teasers linking to
  `docs/how-it-works`, `docs/model-scripts`, `docs/cli` and `docs/troubleshooting` (each `.md` + `.ko.md`).
  When you change one language, change the other; deep detail goes in `docs/`, images in `docs/images/`,
  logos in `.github/logo-{light,dark}.svg`, About/topics in `.github/repo-meta.yml`. Contributor info: `CONTRIBUTING.md`.

## CLI (`VT` = `py -m voxtool` / `python3 -m voxtool` / `voxtool`)
```
VT build models/<name>.py [--open] [--no-score]    # .vox + previews + score (if there is a REFERENCE)
VT score models/<name>.py                          # score only (JSON)
VT fit-camera models/<name>.py [--fovs 0,25,45]    # prints the best-fitting VIEW + _fit.png
VT angles models/<name>.py 30,20 42,15,30          # several az,el[,fov] next to the reference
VT render <file.vox> [--az --el --fov]             # preview for any .vox
VT open <file.vox> / VT shot                       # open in MagicaVoxel / capture its window (Windows)
VT ref grid|crop|sample|palette|cutout <img> ...   # reference study
VT extrude <img> --name N [--depth 4 --inflate]    # pixel art -> voxels (no Claude)
VT carve --front f [--side s --top t] --name N     # silhouettes -> voxels (no Claude)
VT sprites|export|recolor models/<name>.py ...     # game assets
VT ui / VT install-skill
```

## Coordinates / DSL rules
- Array `[x, y, z]`, **z is up**, **y=0 is the front** (the side MagicaVoxel's default camera looks at — verified).
- Boxes are position + size: `m.box(x, y, z, w, d, h, color)`. Anything outside the grid is clipped. `color=None` carves.
- A `region=` tuple is always `(x, y, z, w, d, h)` (z is third!). Getting the order wrong once produced zero flowers —
  check the per-colour counts in stats.
- Register colours with `m.pal.add(name, hex, emit=..)` and use them by name. Max 255 colours. Lights use `emit>0`.
- For kit sheets with several pieces, draw each inside `with m.part("name"):` → each piece is saved as its own object
  in the .vox (movable separately in MagicaVoxel). The whole grid may then exceed 256; only each piece must be ≤ 256.
  Example: `models/model_1027_2140.py` (imports player_house, pastes it in and adds 6 pieces).
- Put key dimensions in constants at the top of the script (`FLOOR`, `EAVE`, …) and derive every other coordinate from
  them, so fixing a proportion is a one-line change. (Writing literal coordinates once meant rewriting everything when
  the depth changed.)

## Reproducing a reference (lessons from the player house)
- References are usually **perspective renders**. Don't measure in screen pixels; measure **relative to an element of
  known size (door ≈ 21 voxels)**. Setting `fov` in `VIEW` makes the preview perspective, and `fit-camera` finds whether
  orthographic or perspective fits better.
- Fix the camera first (`fit-camera`). Then proportions → silhouette (red/blue in the score image) → colour → details.
- The score is an observation, not the goal: if something sticking out to the front would hide the door or windows,
  prefer keeping the key visible elements over a higher score.
- Colour calibration: the preview shades the front ×0.9 and the left side ×0.76. A front colour sampled from the
  reference ÷ 0.9 ≈ the base colour.
- Build order: walls → `bricks()` texture → roof → openings (carving) → decoration → plants (last, `only_empty`).
- For the final check, `--open` and then `VT shot` to see that it really loaded in MagicaVoxel.
