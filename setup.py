"""Build steps pyproject.toml can't express (everything else is configured there).

- The /voxelize skill lives in .claude/skills/voxelize, where Claude Code finds it in a checkout;
  the wheel carries a copy as voxtool/skill/, so `voxtool install-skill` and the web UI work after
  `pip install 2dtovoxel` too.
- PyPI shows README.md without the repository around it: relative links and images are pointed
  at GitHub, and the mermaid diagram (PyPI doesn't draw it) becomes a link.
"""
import re
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

HERE = Path(__file__).resolve().parent
SKILL = HERE / ".claude" / "skills" / "voxelize"
REPO = "https://github.com/NangManCatDev/2DtoVoxel"
RAW = "https://raw.githubusercontent.com/NangManCatDev/2DtoVoxel/main"
LINK = re.compile(r"(\]\(|^\[[^\]]+\]: )(?!https?://|mailto:)([^)\s]+)", re.M)


class BuildPy(build_py):
    def run(self):
        super().run()
        if SKILL.is_dir():
            shutil.copytree(SKILL, Path(self.build_lib) / "voxtool" / "skill", dirs_exist_ok=True)


def pypi_readme(text: str) -> str:
    text = re.sub(r"```mermaid\n.*?```", f"*Diagram: [How it works]({REPO}#how-it-works) on GitHub.*", text, flags=re.S)

    def absolute(m):
        target = m.group(2)
        if target.startswith("#"):
            return m.group(1) + REPO + target
        if re.search(r"\.(png|jpe?g|gif|webp|svg)$", target, re.I):
            return m.group(1) + f"{RAW}/{target}"
        return m.group(1) + f"{REPO}/blob/main/{target}"

    return LINK.sub(absolute, text)


if __name__ == "__main__":
    setup(cmdclass={"build_py": BuildPy},
          long_description=pypi_readme((HERE / "README.md").read_text(encoding="utf-8")),
          long_description_content_type="text/markdown")
