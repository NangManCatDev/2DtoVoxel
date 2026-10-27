"""Server-side user-facing messages in the UI's languages (English / Korean).

The page sends its language in the X-Lang header; errors are raised as
UserError(key, **params) and rendered in that language by the server.
"""
from __future__ import annotations

LANGS = ("en", "ko")

MESSAGES = {
    "bad_name": {
        "en": "Model name must start with a lowercase letter and use only lowercase letters, digits and _ (2-41 characters).",
        "ko": "모델 이름은 영문 소문자로 시작하고 소문자/숫자/_ 만 쓸 수 있습니다 (2~41자).",
    },
    "bad_model": {"en": "Unknown Claude model.", "ko": "알 수 없는 Claude 모델입니다."},
    "bad_kind": {"en": "Unknown job type.", "ko": "알 수 없는 작업 종류입니다."},
    "no_script": {"en": "models/{name}.py does not exist.", "ko": "models/{name}.py 가 없습니다."},
    "no_reference": {"en": "Choose a reference image.", "ko": "레퍼런스 이미지를 선택하세요."},
    "exists": {
        "en": "models/{name}.py already exists. Pick another name, or use \"Request changes\" on the existing model.",
        "ko": "models/{name}.py 가 이미 있습니다. 다른 이름을 쓰거나 기존 모델에서 '수정 요청'을 사용하세요.",
    },
    "no_request": {"en": "Describe the change you want.", "ko": "수정 요청 내용을 입력하세요."},
    "no_vox": {"en": "There is no .vox file yet.", "ko": "아직 .vox 파일이 없습니다."},
    "not_image": {"en": "Only image files can be uploaded.", "ko": "이미지 파일만 올릴 수 있습니다."},
    "busy": {"en": "'{name}' already has a running job.", "ko": "'{name}' 모델에 이미 진행 중인 작업이 있습니다."},
    "no_claude": {
        "en": "Claude Code CLI not found. Set the CLAUDE_CLI environment variable to the claude executable.",
        "ko": "Claude Code CLI를 찾지 못했습니다. CLAUDE_CLI 환경변수로 claude 실행 파일을 지정하세요.",
    },
    "no_magicavoxel": {
        "en": "MagicaVoxel not found. Set the MAGICAVOXEL_EXE environment variable to MagicaVoxel.exe.",
        "ko": "MagicaVoxel을 찾지 못했습니다. MAGICAVOXEL_EXE 환경변수로 MagicaVoxel.exe를 지정하세요.",
    },
    "bad_iteration": {"en": "That version is not available.", "ko": "그 버전을 찾을 수 없습니다."},
    "bad_format": {"en": "Unknown export format.", "ko": "알 수 없는 내보내기 형식입니다."},
    "shot_failed": {
        "en": "Could not capture the MagicaVoxel window. Is MagicaVoxel running?",
        "ko": "MagicaVoxel 창을 캡처하지 못했습니다. MagicaVoxel이 실행 중인지 확인하세요.",
    },
}


class UserError(Exception):
    def __init__(self, key: str, **params):
        super().__init__(key)
        self.key, self.params = key, params

    def render(self, lang: str) -> str:
        return MESSAGES[self.key][lang if lang in LANGS else "en"].format(**self.params)


def pick_lang(value: str | None) -> str:
    """'ko', 'ko-KR,ko;q=0.9,...' -> 'ko'; anything else -> 'en'."""
    return "ko" if value and value.strip().lower().startswith("ko") else "en"
