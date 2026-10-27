# Contributing

Thanks for helping. Issues and pull requests are welcome; for bigger changes, open an issue first so we can agree on the approach.

## Set up

```bash
git clone https://github.com/NangManCatDev/2DtoVoxel.git
cd 2DtoVoxel
python -m pip install -e ".[dev]"
python -m pytest -q
```

The tests build models, score them, convert, export, run the CLI and start the real UI server in temporary workspaces (about 10 seconds). CI runs them on Windows and Ubuntu with Python 3.10 and 3.12.

## Project structure

```text
2DtoVoxel/
├─ 2DtoVoxel.bat / 2dtovoxel.sh   launchers for the web UI (Windows / macOS, Linux)
├─ reference/                     input images
├─ models/                        one build script per model (+ <name>.base.vox for conversions)
├─ voxtool/                       library + CLI (`voxtool`)
│  ├─ vox_io.py                   .vox reader/writer, MagicaVoxel-edit backups
│  ├─ model.py                    building DSL (Model, Palette)
│  ├─ render.py                   Camera (orthographic / perspective), previews
│  ├─ reftools.py                 reference study tools, background cutout
│  ├─ score.py                    measured comparison, camera fitting
│  ├─ convert.py                  extrude / carve (no Claude)
│  ├─ export.py                   meshes, sprite sheets, palette variants
│  ├─ __main__.py                 the CLI
│  └─ ui/                         web UI (server.py, jobs.py, i18n.py, static/)
├─ tests/                         pytest suite
├─ docs/                          documentation and README images
├─ output/                        generated files (git-ignored)
├─ .claude/skills/voxelize/       the /voxelize skill
└─ CLAUDE.md                      conventions for Claude Code working in this repo
```

How the parts fit together is described in [docs/how-it-works.md](docs/how-it-works.md).

## Conventions

- **Two languages.** The UI, the README and the docs exist in English and Korean. Add new UI text to both languages in `voxtool/ui/static/i18n.js` (same keys), server messages to `voxtool/ui/i18n.py`, and Claude prompts to `PROMPTS` in `voxtool/ui/jobs.py`. When you change `README.md` or a file in `docs/`, change its `.ko.md` counterpart too.
- **UI job permissions.** Claude jobs started by the UI may only edit their own model script and `output/`, and run voxtool commands for their own model (`allowed_tools` in `voxtool/ui/jobs.py`). Keep the `/voxelize` workflow runnable with voxtool commands alone, and don't widen these permissions without a good reason; see [SECURITY.md](SECURITY.md).
- **Tests.** Add or update a test for behaviour you change. Keep tests fast and self-contained (they use temporary workspaces, no network).
- **Changelog.** Add a line to [CHANGELOG.md](CHANGELOG.md) for user-visible changes.

## Reporting bugs

Open an issue with what you ran, what you expected and what happened. For a problem with a generated model, attach the reference image and the job's log (`output/_jobs/<id>/job.json`) if you can. Security problems: see [SECURITY.md](SECURITY.md).
