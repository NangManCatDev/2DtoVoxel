"""Background jobs for the UI: voxtool commands and headless Claude Code runs.

A Claude job runs `claude -p` in the workspace with the prompt on stdin and
`--output-format stream-json`; each event becomes a log entry the page polls.
Every time Claude builds its model, the script, the comparison/score images and the
score are snapshotted as an "iteration" under output/_jobs/<id>/iter/, so the page can
show progress and restore any earlier version of the script.
"""
from __future__ import annotations

import glob
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .i18n import UserError

ROOT = Path.cwd().resolve()          # the workspace: models/, reference/, output/
JOBS_DIR = ROOT / "output" / "_jobs"
SCORE_RE = re.compile(r"score: iou=([\d.]+) dE=([\d.]+)(.*)")


# ---------------------------------------------------------------- how Claude calls voxtool

_VT: str | None = None


def voxtool_command() -> str:
    """The exact command prefix Claude must use for voxtool on this machine (it appears in
    the prompt and in the permission rules, which must match): `py -m voxtool` on Windows,
    `python3 -m voxtool` elsewhere — whichever interpreter can import the dependencies."""
    global _VT
    if _VT:
        return _VT
    cands = (["py", "python", "python3"] if os.name == "nt" else ["python3", "python"])
    for exe in cands:
        if not shutil.which(exe):
            continue
        r = subprocess.run([exe, "-c", "import numpy, PIL, scipy"], capture_output=True, cwd=ROOT)
        if r.returncode == 0:
            _VT = f"{exe} -m voxtool"
            return _VT
    _VT = f"{Path(sys.executable).stem} -m voxtool"
    return _VT


def allowed_tools(name: str) -> list[str]:
    """What a headless run for model `name` may do; anything else is denied (permission
    mode dontAsk). File edits only in its own script and output/, Bash only voxtool
    commands (no `-c` code), and build/score only for this model, so a job can neither
    change shared code nor rebuild (overwrite) another model's .vox."""
    vt, script = voxtool_command(), f"models/{name}.py"
    own = [f"Bash({vt} {cmd} {script}:*)" for cmd in ("build", "angles", "score", "fit-camera")]
    return ["Read", "Glob", "Grep", "Skill", f"Edit({script})", "Edit(output/**)", *own,
            f"Bash({vt} ref:*)", f"Bash({vt} render:*)", f"Bash({vt} compare:*)", "Bash(ls:*)"]


# ---------------------------------------------------------------- prompts

# Instructions sent to Claude, in the language picked in the UI (Claude also answers in it).
PROMPTS = {
    "en": {
        "rules": """\
This job was started automatically by the 2DtoVoxel web UI. You cannot ask the user questions, so use your judgment and carry it through to the end.
- The working directory is already the project root. Run voxtool exactly as `{vt} ...`.
- You may only create or edit models/{name}.py and files under output/. Do not modify voxtool/, CLAUDE.md, .claude/ or other models; if the library lacks something, write a helper function inside models/{name}.py.
- Bash allows only `{vt} build|angles|score|fit-camera models/{name}.py ...`, `{vt} ref|render|compare ...` and `ls ...` (no `-c` code, no other scripts, no cd or && chaining).
- Never build another model: that would overwrite its .vox, which may contain the user's hand edits.
- Each build prints `score: iou=… dE=… worst: …` (silhouette overlap with the reference, colour difference, worst regions) and writes output/{name}/{name}_score.png (red = missing, blue = extra). Use the numbers together with the images; stop iterating when the score stops improving for two builds in a row.{limit}
- Put any temporary files in output/_scratch/.
- Do not open MagicaVoxel (--open) or take screenshots (shot); the UI handles that.
- Finish with a short reply in English: what you built or changed, the final score, and how it differs from the reference.""",
        "limit": "\n- Build at most {n} times in this job.",
        "generate": """\
Follow .claude/skills/voxelize/SKILL.md to turn the reference image into a MagicaVoxel model.
- Reference: {reference}
- Model name (slug): {name}  → script models/{name}.py, NAME = "{name}", REFERENCE = "{reference}"
- Extra requests: {notes}""",
        "none": "none",
        "refine": """\
Modify the existing model models/{name}.py as requested below. ({ref})
Request: {notes}

Steps: read and edit the script → `{vt} build models/{name}.py` → check output/{name}/{name}_compare.png,
_score.png and _sheet.png with Read → repeat until the request is met. Leave unrelated parts unchanged.""",
        "ref": "Reference: {reference}",
        "no_ref": "no reference",
    },
    "ko": {
        "rules": """\
이 작업은 2DtoVoxel 웹 UI가 자동으로 실행했다. 사용자에게 질문할 수 없으니 합리적으로 판단해 끝까지 진행해.
- 작업 디렉터리는 이미 프로젝트 루트다. voxtool은 정확히 `{vt} ...` 형태로 실행한다.
- 만들거나 고칠 수 있는 파일은 models/{name}.py 와 output/ 아래뿐이다. voxtool/, CLAUDE.md, .claude/, 다른 모델은 수정하지 마. 라이브러리에 없는 기능은 models/{name}.py 안에 헬퍼 함수로 작성해.
- Bash는 `{vt} build|angles|score|fit-camera models/{name}.py ...`, `{vt} ref|render|compare ...`, `ls ...`만 허용된다(`-c` 코드, 다른 스크립트, cd, && 연결 불가).
- 다른 모델은 절대 빌드하지 마. 그 모델의 .vox(사용자가 손으로 고친 내용이 있을 수 있음)를 덮어쓴다.
- 빌드할 때마다 `score: iou=… dE=… worst: …`(레퍼런스와의 실루엣 겹침, 색 차이, 가장 어긋난 영역)가 출력되고 output/{name}/{name}_score.png(빨강=빠짐, 파랑=넘침)가 만들어진다. 숫자와 이미지를 함께 보고 고치고, 점수가 두 번 연속 오르지 않으면 반복을 멈춰라.{limit}
- 임시 파일이 필요하면 output/_scratch/ 에 둔다.
- MagicaVoxel 열기(--open)와 화면 캡처(shot)는 하지 않는다. UI가 따로 처리한다.
- 마지막 답변은 한국어로 짧게: 무엇을 만들었/바꿨는지, 최종 점수, 레퍼런스와 다른 점.""",
        "limit": "\n- 이 작업에서 빌드는 최대 {n}번까지만 한다.",
        "generate": """\
.claude/skills/voxelize/SKILL.md 절차대로 레퍼런스 이미지를 MagicaVoxel 모델로 만들어.
- 레퍼런스: {reference}
- 모델 이름(slug): {name}  → 스크립트 models/{name}.py, NAME = "{name}", REFERENCE = "{reference}"
- 추가 요청: {notes}""",
        "none": "없음",
        "refine": """\
기존 모델 models/{name}.py 를 아래 요청대로 수정해. ({ref})
요청: {notes}

절차: 스크립트를 읽고 수정 → `{vt} build models/{name}.py` → output/{name}/{name}_compare.png, _score.png,
_sheet.png 를 Read로 확인 → 요청이 반영될 때까지 반복. 요청과 무관한 부분은 바꾸지 마.""",
        "ref": "레퍼런스: {reference}",
        "no_ref": "레퍼런스 없음",
    },
}


def _rules(p: dict, name: str, max_builds: int | None) -> str:
    limit = p["limit"].format(n=max_builds) if max_builds else ""
    return p["rules"].format(name=name, vt=voxtool_command(), limit=limit)


def generate_prompt(name: str, reference: str, notes: str, lang: str = "en", max_builds: int | None = None) -> str:
    p = PROMPTS[lang]
    body = p["generate"].format(name=name, reference=reference, notes=notes.strip() or p["none"])
    return f"{_rules(p, name, max_builds)}\n\n{body}"


def refine_prompt(name: str, reference: str | None, notes: str, lang: str = "en",
                  max_builds: int | None = None) -> str:
    p = PROMPTS[lang]
    ref = p["ref"].format(reference=reference) if reference else p["no_ref"]
    body = p["refine"].format(name=name, ref=ref, notes=notes.strip(), vt=voxtool_command())
    return f"{_rules(p, name, max_builds)}\n\n{body}"


# ---------------------------------------------------------------- Claude CLI

def find_claude() -> str | None:
    env = os.environ.get("CLAUDE_CLI")
    if env and os.path.isfile(env):
        return env
    hit = shutil.which("claude")
    if hit:
        return hit
    home = Path.home()
    cands = []
    for ext_dir in (".vscode", ".vscode-insiders", ".cursor"):
        for exe in ("claude.exe", "claude"):
            cands += glob.glob(str(home / ext_dir / "extensions" / "anthropic.claude-code-*" /
                                   "resources" / "native-binary" / exe))

    def version(p: str):
        m = re.search(r"claude-code-(\d+)\.(\d+)\.(\d+)", p)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    return max(cands, key=version) if cands else None


def _kill_tree(proc: subprocess.Popen):
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.kill()


# ---------------------------------------------------------------- jobs

class Job:
    def __init__(self, kind: str, name: str, title: str, meta: dict | None = None):
        self.id = time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
        self.kind = kind            # build | generate | refine | convert | export
        self.name = name            # model slug
        self.title = title
        self.meta = meta or {}
        self.status = "running"     # running | done | error | cancelled
        self.started = time.time()
        self.ended: float | None = None
        self.log: list[dict] = []
        self.iterations: list[dict] = []
        self.proc: subprocess.Popen | None = None
        self._snap = 0
        self._pending: dict[str, tuple[str, dict]] = {}   # tool_use id -> (tool, input)
        self._lock = threading.Lock()

    @property
    def dir(self) -> Path:
        return JOBS_DIR / self.id

    def add(self, kind: str, text: str = "", **extra):
        with self._lock:
            self.log.append({"t": time.time(), "kind": kind, "text": text, **extra})

    def summary(self) -> dict:
        best = max((i["iou"] for i in self.iterations if i.get("iou") is not None), default=None)
        return {"id": self.id, "kind": self.kind, "name": self.name, "title": self.title,
                "status": self.status, "started": self.started, "ended": self.ended, "meta": self.meta,
                "builds": sum(1 for i in self.iterations if i["n"] > 0), "best_iou": best}

    def detail(self, since: int = 0) -> dict:
        with self._lock:
            entries = self.log[since:]
            n = len(self.log)
        return {**self.summary(), "log": entries, "next": n, "iterations": self.iterations}

    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "job.json").write_text(json.dumps(self.detail(), ensure_ascii=False), encoding="utf-8")

    def finish(self, status: str):
        if self.status == "running":
            self.status = status
        self.ended = time.time()
        self.save()


class JobManager:
    def __init__(self, file_url):
        self.jobs: dict[str, Job] = {}
        self.file_url = file_url    # Path -> URL served by the UI
        self._load_history()

    # ------------------------------------------------------------ queries

    def list(self) -> list[dict]:
        return [j.summary() for j in sorted(self.jobs.values(), key=lambda j: j.started, reverse=True)]

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def running_for(self, name: str) -> Job | None:
        for j in self.jobs.values():
            if j.name == name and j.status == "running":
                return j
        return None

    def last_session(self, name: str) -> str | None:
        """Session of the latest finished Claude job for this model (for --resume)."""
        for j in sorted(self.jobs.values(), key=lambda j: j.started, reverse=True):
            if j.name == name and j.kind in ("generate", "refine") and j.meta.get("session_id"):
                return j.meta["session_id"]
        return None

    # ------------------------------------------------------------ starting

    def start_voxtool(self, kind: str, name: str, args: list[str], meta: dict | None = None) -> Job:
        """A plain voxtool command (build, convert, export) run with this interpreter."""
        job = self._new(kind, name, f"{kind} · {name}", meta)
        cmd = [sys.executable, "-m", "voxtool", *args]
        threading.Thread(target=self._run_plain, args=(job, cmd), daemon=True).start()
        return job

    def start_build(self, name: str, meta: dict | None = None) -> Job:
        return self.start_voxtool("build", name, ["build", f"models/{name}.py"], meta)

    def start_claude(self, kind: str, name: str, prompt: str, model: str = "", meta: dict | None = None, *,
                     budget: float | None = None, max_builds: int | None = None, resume: str | None = None) -> Job:
        exe = find_claude()
        if not exe:
            raise UserError("no_claude")
        meta = dict(meta or {}, budget=budget, max_builds=max_builds, resumed=bool(resume))
        job = self._new(kind, name, f"{kind} · {name}", meta)
        (ROOT / "output" / "_scratch").mkdir(parents=True, exist_ok=True)  # the prompt points Claude here
        cmd = [exe, "-p", "--output-format", "stream-json", "--verbose",
               "--permission-mode", "dontAsk", "--allowedTools", *allowed_tools(name)]
        if model:
            cmd += ["--model", model]
        if budget:
            cmd += ["--max-budget-usd", f"{budget:g}"]
        if resume:
            cmd += ["--resume", resume]
        # log entries with a `key` are worded by the page in its current language
        job.add("info", key="claude_start", model=model)
        job.add("prompt", prompt)
        self._snapshot(job, 0, label="before")
        threading.Thread(target=self._run_claude, args=(job, cmd, prompt), daemon=True).start()
        return job

    def cancel(self, job_id: str, key: str = "cancelled") -> bool:
        job = self.jobs.get(job_id)
        if not job or job.status != "running":
            return False
        job.status = "cancelled"
        job.add("error", key=key)
        if job.proc:
            _kill_tree(job.proc)
        return True

    def restore(self, job_id: str, n: int) -> Job:
        """Puts the script from iteration n back into models/<name>.py (the current script
        is kept next to the snapshots first) and rebuilds."""
        job = self.jobs.get(job_id)
        it = next((i for i in (job.iterations if job else []) if i["n"] == n and i.get("script_path")), None)
        if not it:
            raise UserError("bad_iteration")
        if self.running_for(job.name):
            raise UserError("busy", name=job.name)
        script = ROOT / "models" / f"{job.name}.py"
        if script.exists():
            keep = job.dir / "iter" / f"replaced_{time.strftime('%Y%m%d-%H%M%S')}_{job.name}.py"
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(script, keep)
        shutil.copyfile(ROOT / it["script_path"], script)
        build = self.start_build(job.name, {"restored_from": job_id, "iteration": n})
        build.add("info", key="restored", job=job_id, n=n)
        return build

    def _new(self, kind, name, title, meta=None) -> Job:
        if self.running_for(name):
            raise UserError("busy", name=name)
        job = Job(kind, name, title, meta)
        self.jobs[job.id] = job
        return job

    # ------------------------------------------------------------ runners

    def _popen(self, cmd, stdin=None) -> subprocess.Popen:
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=stdin, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)

    def _run_plain(self, job: Job, cmd: list[str]):
        try:
            job.proc = self._popen(cmd)
            for raw in job.proc.stdout:
                line = raw.decode("utf-8", "replace").rstrip()
                if line:
                    job.add("output", line)
            code = job.proc.wait()
            if code != 0:
                job.add("error", key="exit_code", code=code)
            job.finish("done" if code == 0 else "error")
        except Exception as e:  # noqa: BLE001 - surface anything to the page
            job.add("error", str(e))
            job.finish("error")

    def _run_claude(self, job: Job, cmd: list[str], prompt: str):
        ok = False
        try:
            job.proc = self._popen(cmd, stdin=subprocess.PIPE)
            job.proc.stdin.write(prompt.encode("utf-8"))
            job.proc.stdin.close()
            for raw in job.proc.stdout:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    job.add("info", line)
                    continue
                ok = self._handle_event(job, ev) or ok
            code = job.proc.wait()
            if job.status == "running" and code != 0 and not ok:
                job.add("error", key="claude_exit", code=code)
            job.finish("done" if ok else "error")
        except Exception as e:  # noqa: BLE001
            job.add("error", str(e))
            job.finish("error")

    def _handle_event(self, job: Job, ev: dict) -> bool:
        """Turns one stream-json event into log entries. Returns True on a successful result."""
        t = ev.get("type")
        if t == "system" and ev.get("subtype") == "init":
            job.meta["session_id"] = ev.get("session_id")
            job.add("info", key="session", model=ev.get("model", ""))
        elif t == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "text" and c.get("text", "").strip():
                    job.add("text", c["text"].strip())
                elif c.get("type") == "tool_use":
                    job._pending[c.get("id", "")] = (c.get("name", ""), c.get("input") or {})
                    self._tool_entry(job, c.get("name", ""), c.get("input") or {})
        elif t == "user":
            for c in ev.get("message", {}).get("content", []):
                if not isinstance(c, dict) or c.get("type") != "tool_result":
                    continue
                body = c.get("content")
                if isinstance(body, list):
                    body = "\n".join(b.get("text", "") for b in body if isinstance(b, dict))
                body = (body or "").strip()
                tool, inp = job._pending.pop(c.get("tool_use_id", ""), ("", {}))
                if c.get("is_error"):
                    job.add("error", body[:1500])
                elif body and not body.startswith("<") and len(body) < 4000:
                    job.add("output", body[:1500])
                if tool == "Bash" and not c.get("is_error") and self._is_own_build(job, inp.get("command", "")):
                    self._on_build(job, body)
        elif t == "result":
            ok = not ev.get("is_error") and ev.get("subtype") == "success"
            job.meta["cost_usd"] = ev.get("total_cost_usd")
            job.meta["duration_ms"] = ev.get("duration_ms")
            text = str(ev.get("result") or "").strip()
            texts = [e for e in job.log if e["kind"] == "text"]
            if texts and texts[-1]["text"] == text:
                text = ""  # already shown as the last reply
            job.add("result", text, ok=ok,
                    cost=ev.get("total_cost_usd"), duration=ev.get("duration_ms"), turns=ev.get("num_turns"))
            return ok
        return False

    # ------------------------------------------------------------ iterations

    @staticmethod
    def _is_own_build(job: Job, command: str) -> bool:
        return re.search(rf"\bbuild\s+models/{re.escape(job.name)}\.py\b", command) is not None

    def _on_build(self, job: Job, output: str):
        n = sum(1 for i in job.iterations if i["n"] > 0) + 1
        m = SCORE_RE.search(output)
        score = {"iou": float(m.group(1)), "delta_e": float(m.group(2)),
                 "worst": m.group(3).replace("worst:", "").strip()} if m else {}
        it = self._snapshot(job, n, **score)
        job.add("iteration", n=n, iou=it.get("iou"), delta_e=it.get("delta_e"), worst=it.get("worst", ""),
                image=it.get("score") or it.get("compare"))
        job.save()
        limit = job.meta.get("max_builds")
        if limit and n >= limit + 2:          # the prompt asks for at most `limit`; stop runaway jobs
            self.cancel(job.id, key="limit_reached")

    def _snapshot(self, job: Job, n: int, label: str = "", **score) -> dict:
        """Copies models/<name>.py and the current previews into output/_jobs/<id>/iter/."""
        d = job.dir / "iter"
        d.mkdir(parents=True, exist_ok=True)
        it: dict = {"n": n, "t": time.time(), "label": label, **score}
        script = ROOT / "models" / f"{job.name}.py"
        if script.exists():
            dst = d / f"{n:02d}_{job.name}.py"
            shutil.copyfile(script, dst)
            it["script_path"] = dst.relative_to(ROOT).as_posix()
            it["script"] = self.file_url(dst)
        out = ROOT / "output" / job.name
        for kind in ("compare", "score", "iso"):
            src = out / f"{job.name}_{kind}.png"
            if n > 0 and src.exists():
                dst = d / f"{n:02d}_{kind}.png"
                shutil.copyfile(src, dst)
                it[kind] = self.file_url(dst)
        if "script_path" in it or n > 0:
            job.iterations.append(it)
        return it

    # ------------------------------------------------------------ log entries for tools

    def _tool_entry(self, job: Job, name: str, inp: dict):
        if name == "Bash":
            job.add("tool", inp.get("command", ""), tool="Bash")
        elif name in ("Read", "Write", "Edit"):
            fp = inp.get("file_path", "")
            entry = {"tool": name}
            img = self._image_for(job, fp) if name == "Read" else None
            if img:
                entry["image"] = img
            job.add("tool", self._rel(fp), **entry)
        elif name in ("Glob", "Grep"):
            job.add("tool", inp.get("pattern", ""), tool=name)
        elif name == "Skill":
            job.add("tool", inp.get("skill", ""), tool="Skill")
        else:
            job.add("tool", json.dumps(inp, ensure_ascii=False)[:300], tool=name)

    def _rel(self, fp: str) -> str:
        try:
            return Path(fp).resolve().relative_to(ROOT).as_posix()
        except (ValueError, OSError):
            return fp

    def _image_for(self, job: Job, fp: str) -> str | None:
        """URL of an image Claude is reading; output/ images are copied so the log
        keeps that iteration even after the file is rebuilt."""
        try:
            p = Path(fp).resolve()
            rel = p.relative_to(ROOT)
        except (ValueError, OSError):
            return None
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp") or not p.is_file():
            return None
        if rel.parts[0] == "output" and "_jobs" not in rel.parts:
            job._snap += 1
            job.dir.mkdir(parents=True, exist_ok=True)
            dst = job.dir / f"{job._snap:02d}_{p.name}"
            shutil.copyfile(p, dst)
            return self.file_url(dst)
        return self.file_url(p)

    # ------------------------------------------------------------ history

    def _load_history(self):
        for f in sorted(JOBS_DIR.glob("*/job.json"))[-80:]:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            job = Job(d["kind"], d["name"], d["title"], d.get("meta"))
            job.id, job.status = d["id"], d["status"]
            if job.status == "running":       # server died mid-run
                job.status = "error"
            job.started, job.ended, job.log = d["started"], d.get("ended"), d.get("log", [])
            job.iterations = d.get("iterations", [])
            self.jobs[job.id] = job
