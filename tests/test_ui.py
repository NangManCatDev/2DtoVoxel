"""UI job logic (permissions, prompts, iterations, restore) and the HTTP server."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

from conftest import REPO
from voxtool.ui import jobs


def test_permissions_are_scoped_to_one_model():
    tools = jobs.allowed_tools("hut")
    vt = jobs.voxtool_command()
    assert vt.endswith("-m voxtool")
    assert "Edit(models/hut.py)" in tools and "Edit(output/**)" in tools
    assert "Edit" not in tools and "Write" not in tools          # no unscoped file writes
    for shell in jobs.SHELL_TOOLS:                                # same rules for Bash and PowerShell
        assert f"{shell}({vt} build models/hut.py:*)" in tools
        assert f"{shell}({vt} ref:*)" in tools
        assert not any(t.startswith(f"{shell}(py:") or t == shell for t in tools)


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_prompts_name_the_model_command_and_limit(lang):
    vt = jobs.voxtool_command()
    g = jobs.generate_prompt("hut", "reference/hut.png", "", lang, max_builds=5)
    r = jobs.refine_prompt("hut", "reference/hut.png", "make it red", lang)
    for p in (g, r):
        assert "models/hut.py" in p and f"{vt} build" in p and "{" not in p
        assert "hut_turn.png" in p and "loose:" in p and "(thin)" in p      # the checks the score can't see
    assert "5" in g and "make it red" in r


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "JOBS_DIR", tmp_path / "output" / "_jobs")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "hut.py").write_text("VERSION = 1\n", encoding="utf-8")
    return jobs.JobManager(lambda p: "/files/" + p.relative_to(tmp_path).as_posix())


def _fake_build(mgr, job, tool_id, output, tool="Bash"):
    vt = jobs.voxtool_command()
    mgr._handle_event(job, {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_id, "name": tool, "input": {"command": f"{vt} build models/hut.py"}}]}})
    mgr._handle_event(job, {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": output}]}})


def test_builds_become_iterations_and_restore_brings_a_version_back(manager, tmp_path):
    job = manager._new("refine", "hut", "refine · hut")
    manager._snapshot(job, 0, label="before")
    (tmp_path / "models" / "hut.py").write_text("VERSION = 2\n", encoding="utf-8")
    _fake_build(manager, job, "t1", "built hut\nscore: iou=0.812 dE=14.3 worst: top missing 12%")
    (tmp_path / "models" / "hut.py").write_text("VERSION = 3\n", encoding="utf-8")
    _fake_build(manager, job, "t2", "built hut\nscore: iou=0.901 dE=9.0", tool="PowerShell")
    job.finish("done")

    assert [i["n"] for i in job.iterations] == [0, 1, 2]
    assert [e["text"] for e in job.log if e.get("tool") == "PowerShell"] == [f"{jobs.voxtool_command()} build models/hut.py"]
    assert job.iterations[1]["iou"] == 0.812 and job.iterations[1]["worst"] == "top missing 12%"
    assert job.summary()["best_iou"] == 0.901
    assert any(e["kind"] == "iteration" for e in job.log)

    manager.start_build = lambda name, meta=None: manager._new("build", name, "build", meta)
    manager.restore(job.id, 1)
    assert (tmp_path / "models" / "hut.py").read_text() == "VERSION = 2\n"
    assert list((job.dir / "iter").glob("replaced_*_hut.py"))      # current script was kept
    with pytest.raises(jobs.UserError):
        manager.restore(job.id, 9)


def test_other_models_builds_are_not_iterations(manager):
    job = manager._new("refine", "hut", "refine · hut")
    vt = jobs.voxtool_command()
    manager._handle_event(job, {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "x", "name": "Bash", "input": {"command": f"{vt} build models/hut2.py"}}]}})
    manager._handle_event(job, {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "score: iou=0.5 dE=1"}]}})
    assert job.iterations == []


@pytest.mark.parametrize("requested, session, stopped", [
    ("", "claude-haiku-4-5-20251001", True),
    ("", "claude-opus-5-5", False),
    ("haiku", "claude-haiku-4-5-20251001", False),
])
def test_default_model_that_is_haiku_stops_the_job(manager, requested, session, stopped):
    job = manager._new("generate", "hut", "generate · hut", {"model": requested})
    manager._handle_event(job, {"type": "system", "subtype": "init", "session_id": "s", "model": session})
    assert (job.status == "cancelled") is stopped
    assert any(e.get("key") == "weak_model" for e in job.log) is stopped


# ---------------------------------------------------------------- server (real process)

@pytest.fixture
def server(workspace):
    env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    port = 18700 + os.getpid() % 500
    proc = subprocess.Popen([sys.executable, "-m", "voxtool", "ui", "--no-browser", "--port", str(port)],
                            cwd=workspace, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url = None
    deadline = time.time() + 20
    while time.time() < deadline and not url:
        line = proc.stdout.readline()
        m = re.search(r"(http://127\.0\.0\.1:\d+/)", line or "")
        url = m.group(1) if m else None
    assert url, "server did not start"
    html = urllib.request.urlopen(url).read().decode("utf-8")
    token = re.search(r'name="token" content="([^"]+)"', html).group(1)
    yield url, token
    proc.terminate()
    proc.wait(timeout=10)


def _post(url, body, token=None, lang="en"):
    headers = {"Content-Type": "application/json", "X-Lang": lang}
    if token:
        headers["X-Token"] = token
    req = urllib.request.Request(url, json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_server_api_token_i18n_and_build(server):
    url, token = server
    models = json.loads(urllib.request.urlopen(url + "api/models").read())
    assert [m["slug"] for m in models] == ["hut"]
    assert _post(url + "api/jobs", {"kind": "build", "name": "hut"})[0] == 403       # no token
    code, en = _post(url + "api/jobs", {"kind": "build", "name": "Bad Name"}, token, "en")
    _, ko = _post(url + "api/jobs", {"kind": "build", "name": "Bad Name"}, token, "ko")
    assert code == 400 and en["code"] == "bad_name" and en["error"] != ko["error"]
    code, job = _post(url + "api/jobs", {"kind": "build", "name": "hut"}, token)
    assert code == 200
    for _ in range(100):
        d = json.loads(urllib.request.urlopen(f"{url}api/jobs/{job['id']}").read())
        if d["status"] != "running":
            break
        time.sleep(0.3)
    assert d["status"] == "done"
    detail = json.loads(urllib.request.urlopen(url + "api/models/hut").read())
    assert detail["stats"]["voxels"] > 0 and detail["score_history"] and "score" in detail["images"]


def test_delete_moves_a_model_to_the_trash(server, workspace):
    url, token = server
    (workspace / "models" / "village.py").write_text("from hut import build  # uses hut\nNAME = 'village'\n",
                                                     encoding="utf-8")
    (workspace / "output" / "hut").mkdir(parents=True, exist_ok=True)
    (workspace / "output" / "hut" / "hut.vox").write_bytes(b"VOX ")
    check = json.loads(urllib.request.urlopen(url + "api/models/hut/delete-check").read())
    assert check["items"] == ["models/hut.py", "output/hut/"] and check["used_by"] == ["village"]
    assert _post(url + "api/models/hut/delete", {})[0] == 403                     # no token
    code, r = _post(url + "api/models/hut/delete", {}, token)
    assert code == 200 and r["trash"].startswith("output/_trash/hut_")
    trash = workspace / r["trash"]
    assert (trash / "hut.py").exists() and (trash / "hut" / "hut.vox").exists()
    assert not (workspace / "models" / "hut.py").exists() and not (workspace / "output" / "hut").exists()
    assert (workspace / "reference" / "hut.png").exists()                       # the reference stays
    slugs = [m["slug"] for m in json.loads(urllib.request.urlopen(url + "api/models").read())]
    assert "hut" not in slugs and "village" in slugs
    code, err = _post(url + "api/models/hut/delete", {}, token, "ko")
    assert code == 400 and err["code"] == "no_script"


def test_trash_restore_and_purge(server, workspace):
    url, token = server
    code, r = _post(url + "api/models/hut/delete", {}, token)
    entry = r["trash"].split("/")[-2]
    trash = json.loads(urllib.request.urlopen(url + "api/trash").read())
    assert [e["id"] for e in trash] == [entry] and "hut.py" in trash[0]["items"]
    (workspace / "models" / "hut.py").write_text("NAME = 'hut'\n", encoding="utf-8")       # a new hut in the way
    code, err = _post(url + f"api/trash/{entry}/restore", {}, token)
    assert code == 400 and err["code"] == "restore_conflict" and (workspace / r["trash"] / "hut.py").exists()
    (workspace / "models" / "hut.py").unlink()
    code, ok = _post(url + f"api/trash/{entry}/restore", {}, token)
    assert code == 200 and "models/hut.py" in ok["restored"] and (workspace / "models" / "hut.py").exists()
    assert json.loads(urllib.request.urlopen(url + "api/trash").read()) == []
    _post(url + "api/models/hut/delete", {}, token)
    assert _post(url + "api/trash/purge", {})[0] == 403                           # no token
    code, gone = _post(url + "api/trash/purge", {}, token)
    assert code == 200 and gone["removed"] == 1 and not any((workspace / "output" / "_trash").iterdir())
    assert _post(url + "api/trash/../models/restore", {}, token)[0] in (400, 404)
