# Troubleshooting, tips and limitations

**English** | [한국어](troubleshooting.ko.md) · ← [Back to README](../README.md)

## Troubleshooting

| Symptom | What to do |
|---|---|
| "Claude Code" chip is red | The CLI wasn't found. Install Claude Code and log in, or set `CLAUDE_CLI`, then restart the UI |
| "MagicaVoxel" chip is red | Set `MAGICAVOXEL_EXE`, then restart the UI. Everything except open / capture still works |
| The browser didn't open | Open the address printed in the console window yourself |
| The 3D tab shows an error | It needs internet access to load three.js from the CDN. The other tabs work offline |
| The score looks wrong | Check `voxtool ref cutout <img>`; for a sheet with several objects set `CUTOUT = {"keep": "all"}` |
| "Capture MagicaVoxel" fails | MagicaVoxel must be running (Windows only). Open the model in it first |
| A job failed or stopped | Open it from "Recent jobs" and read the red entries; use **Restore** on a good build, then retry |
| The UI looks old after updating the code | Close the console window, start the UI again, and reload the page |
| "models/&lt;name&gt;.py already exists" | Pick another name, or open that model and use "Request changes" |

## Tips for good results

- **Use a clear reference**: one object, a 3/4 view, an even background. Check `voxtool ref cutout` once; the score is only as good as the cutout.
- **Say what matters** in "Extra requests": a size limit, details that must be kept, or parts that can be simplified.
- **Set limits** for long runs: a max cost and max builds per job.
- **Change one thing at a time** with "Request changes". Short, concrete requests ("lower the porch roof by 3 voxels") work better than long lists.
- **Start simple images with Quick convert**, then refine with Claude; it is faster and cheaper than generating from scratch.
- **Keep manual edits in a separate file** (MagicaVoxel *Save As*), see below.

## Platform notes and limitations

- **Windows** is where the whole flow (UI, Claude jobs, MagicaVoxel open and capture) has been used. **macOS / Linux**: the CLI and tests run (CI covers Ubuntu), the UI starts Claude jobs with `python3 -m voxtool`, and MagicaVoxel is opened with `open -a` on macOS; window capture (`shot`) is Windows-only, and the full Claude flow there has not been tried by the author yet.
- **"Rebuild" and Claude's changes regenerate the `.vox` from the script.** If the existing file was saved from MagicaVoxel (so it may hold hand edits), it is first copied to `output/<name>/<name>_edited_<time>.vox`, and the model page lists these backups. Hand edits are not carried into the rebuilt model, so to keep working on them, use *Save As* in MagicaVoxel, or start a script from it with `Model.from_vox`.
- Each saved object is limited to 256 voxels per axis and 255 colours (MagicaVoxel's limits); use `m.part()` for bigger scenes.
- The 3D tab loads three.js from a CDN and needs an internet connection.
- Results differ from run to run. Generation takes about 10–30 minutes; the cost depends on the Claude model and your plan.
