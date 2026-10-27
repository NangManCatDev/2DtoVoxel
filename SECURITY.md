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
- run only `voxtool build|angles|score|fit-camera models/<name>.py`, `voxtool ref|render|compare` and `ls`, through Bash or PowerShell; running code directly (`python -c`, other scripts) is refused;
- everything else is denied automatically. Claude Code additionally protects `.claude/`.

Builds back up a `.vox` saved from MagicaVoxel before overwriting it, and every build in a job is snapshotted so earlier script versions can be restored.

### What the allow-list does not do

The allow-list keeps a job from changing the wrong files or rebuilding the wrong model by mistake. It is not a sandbox. The model script a job is allowed to edit is Python, and `build` runs it with your user account's rights, so code written into that script can still read, change or delete files elsewhere and reach the network.

Claude has no reason to write such code for a voxel model, but a reference image with hidden instructions could try to make it. If you need real isolation, run 2DtoVoxel in a virtual machine, a container or under a separate user account.

## Things to keep in mind

- Claude reads your reference images, and their content can steer what it writes into the model script (see above). Only use images you trust, and if a job's log shows anything unexpected, read its model script before building it again.
- Generation uses your Claude Code login; usage counts toward your plan. Set a cost limit per job in the UI if you want a hard cap.
- Don't expose the UI port to a network (for example with port forwarding or a tunnel).

## Reporting a problem

Please open a GitHub issue without exploit details and ask for a private contact, or use GitHub's private vulnerability reporting if it is enabled for the repository.
