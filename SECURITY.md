# Security

2DtoVoxel runs a local web server that can start Claude Code with file access, so it is designed to be reachable only from your own computer and to give each Claude run as little as possible.

## What the UI does to stay local

- The server binds to **127.0.0.1** only.
- Every request that changes something must carry a random token that is generated at startup and embedded in the page; other websites cannot read it.
- Requests whose `Host` header is not `127.0.0.1` or `localhost` are rejected (protects against DNS rebinding).
- Files are served only from `output/` and `reference/`, with path traversal checks.

## What a Claude job may do

Each job runs `claude -p --permission-mode dontAsk` with an allow-list built for that one model (see `allowed_tools` in `voxtool/ui/jobs.py`):

- create or edit only `models/<name>.py` and files under `output/`;
- run only `voxtool build|angles|score|fit-camera models/<name>.py`, `voxtool ref|render|compare` and `ls`; arbitrary code (`python -c`, other scripts) is refused;
- everything else is denied automatically. Claude Code additionally protects `.claude/`.

Builds back up a `.vox` saved from MagicaVoxel before overwriting it, and every build in a job is snapshotted so earlier script versions can be restored.

## Things to keep in mind

- Claude reads your reference images. The allow-list limits what a misleading image could cause, but only use images you trust.
- Generation uses your Claude Code login; usage counts toward your plan. Set a cost limit per job in the UI if you want a hard cap.
- Don't expose the UI port to a network (for example with port forwarding or a tunnel).

## Reporting a problem

Please open a GitHub issue without exploit details and ask for a private contact, or use GitHub's private vulnerability reporting if it is enabled for the repository.
