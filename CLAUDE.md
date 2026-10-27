# 2DtoVoxel

레퍼런스 이미지(`reference/`)를 보고 Claude가 MagicaVoxel 모델(`.vox`)을 만드는 프로젝트.
MagicaVoxel GUI를 조작하지 않는다. **모델 빌드 스크립트(`models/<name>.py`)를 작성 → `.vox` 직접 생성 →
자체 프리뷰 렌더와 정량 점수로 레퍼런스와 비교하며 반복 → MagicaVoxel로 연다.**

새 레퍼런스가 들어오면 `/voxelize <이미지경로>` 스킬(`.claude/skills/voxelize/SKILL.md`)의 절차를 따른다.

## 환경
- Python 3.10+ (numpy, Pillow, scipy). 이 PC는 Windows라 `py -m voxtool ...`; macOS/Linux는 `python3 -m voxtool`.
  `pip install -e .` 하면 `voxtool` 명령도 생긴다. 모든 명령은 워크스페이스(이 폴더)에서 실행.
- MagicaVoxel은 자동 탐색(바탕화면/다운로드/홈/Program Files, macOS `/Applications`), `MAGICAVOXEL_EXE`로 재정의.
- 테스트: `py -m pytest -q` (tests/, 임시 워크스페이스에서 CLI·서버까지 실제로 돌린다). CI는 `.github/workflows/ci.yml`.

## 구조
- `voxtool/vox_io.py` — .vox 읽기/쓰기 (SIZE/XYZI/RGBA/MATL + scene graph). 오브젝트당 축별 최대 256.
  `backup_if_edited()`: MagicaVoxel이 저장한 파일(우리 writer가 안 쓰는 rOBJ/rCAM 등 청크)이면 덮어쓰기 전 복사.
- `voxtool/model.py` — 빌드 DSL (`Model`, `Palette`). 프리미티브, 건축, 유기물, `part()`, `from_vox()/paste_vox()`.
- `voxtool/render.py` — `Camera`(정사영/원근 `fov`), `render_iso`(투명·선명 모드), 정사영 5면 시트.
- `voxtool/reftools.py` — 레퍼런스 분석(그리드, 크롭, 색 샘플, 팔레트) + `cutout()` 배경 제거.
- `voxtool/score.py` — `score_model`(실루엣 IoU, 색 ΔE, 3×3 영역별 빠짐/넘침, diff 이미지), `fit_camera`.
- `voxtool/convert.py` — Claude 없이 변환: `extrude`(픽셀아트 압출/부풀리기), `carve`(다면 실루엣 교차).
- `voxtool/export.py` — greedy 메싱 → OBJ/PLY/GLB, 스프라이트 시트 + manifest.json, 팔레트 변형.
- `voxtool/__main__.py` — CLI 전체. `voxtool/ui/` — 웹 UI (`voxtool ui`, `py -m ui`, `2DtoVoxel.bat`, `2dtovoxel.sh`).
- `models/<name>.py` — 모델별 빌드 스크립트. `NAME`, `REFERENCE`, `VIEW`(+`fov`), 선택: `SCORE_VIEW`, `CUTOUT`.
  변환 결과는 `models/<name>.base.vox`(소스 데이터, 커밋 대상) + 그걸 불러오는 스크립트.
- `output/<name>/` — `.vox`, `_iso/_sheet/_compare/_score/_fit.png`, `_scores.jsonl`, `sprites/ export/ variants/`
  (생성물, 언제든 재생성 가능, git 제외). `output/_jobs/<id>/` — UI 작업 로그와 반복별 스냅샷(`iter/`).

## UI 작업의 권한 (중요)
UI가 Claude를 돌릴 때는 `--permission-mode dontAsk`에 `voxtool/ui/jobs.py`의 `allowed_tools(name)`만 허용한다:
파일 수정은 `models/<name>.py`와 `output/**`만, Bash는 `<VT> build|angles|score|fit-camera models/<name>.py`,
`<VT> ref|render|compare`, `ls`만(`-c` 코드 불가). `<VT>`는 `voxtool_command()`가 OS에 맞게 고른다
(Windows `py -m voxtool`, 그 외 `python3 -m voxtool`) — 지시문과 권한 규칙에 같은 문자열이 들어가야 한다.
그래서 스킬/CLI 절차는 `cd`, `&&`, `-c` 없이 voxtool 명령만으로 돌아가야 하고, 라이브러리에 없는 기능은 모델
스크립트 안에 헬퍼로 쓴다. (UI 작업이 공용 `voxtool/model.py`를 고치고 다른 모델을 다시 빌드해 사용자의
MagicaVoxel 편집을 덮어쓴 적이 있어서 이렇게 막았다.)
- 작업 중 자기 모델을 빌드할 때마다(`build models/<name>.py`의 도구 결과) 스크립트·비교/점수 이미지·점수를
  `output/_jobs/<id>/iter/`에 스냅샷한다. 작업 페이지에서 어느 버전으로든 되돌릴 수 있다(`JobManager.restore`).
- 작업별 비용 상한(`--max-budget-usd`), 빌드 횟수 상한(지시문 + 상한+2에서 강제 중단), 이전 세션 이어서(`--resume`).

## 다국어
- UI는 English/한국어. 화면 문구는 `voxtool/ui/static/i18n.js`(두 언어 같은 키), 서버 오류는 `voxtool/ui/i18n.py`의
  `UserError(key)`, Claude 지시문은 `jobs.py`의 `PROMPTS[lang]`. 문구를 추가할 때는 항상 두 언어를 함께 넣는다.
  작업 로그 항목은 문장 대신 `key`로 저장해서 화면 언어를 바꾸면 지난 로그도 그 언어로 보인다.
- README는 `README.md`(영어)와 `README.ko.md`(한국어). 내용을 바꾸면 둘 다 고치고, 이미지는 `docs/images/`.

## CLI (`VT` = `py -m voxtool`)
```
VT build models/<name>.py [--open] [--no-score]    # .vox + 프리뷰 + (REFERENCE 있으면) 점수
VT score models/<name>.py                          # 점수만 (JSON)
VT fit-camera models/<name>.py [--fovs 0,25,45]    # 가장 잘 맞는 VIEW 출력 + _fit.png
VT angles models/<name>.py 30,20 42,15,30          # az,el[,fov] 여러 개를 레퍼런스 옆에
VT render <file.vox> [--az --el --fov]             # 아무 .vox나 프리뷰
VT open <file.vox> / VT shot                       # MagicaVoxel로 열기 / 창 캡처(Windows)
VT ref grid|crop|sample|palette|cutout <img> ...   # 레퍼런스 분석
VT extrude <img> --name N [--depth 4 --inflate]    # 픽셀아트 -> 복셀 (Claude 없이)
VT carve --front f [--side s --top t] --name N     # 실루엣 -> 복셀 (Claude 없이)
VT sprites|export|recolor models/<name>.py ...     # 게임 에셋
VT ui / VT install-skill
```

## 좌표 / DSL 규칙
- 배열 `[x, y, z]`, **z가 위**, **y=0이 정면**(MagicaVoxel 기본 카메라가 보는 면 — 실제 확인함).
- 박스는 위치+크기: `m.box(x, y, z, w, d, h, color)`. 그리드 밖은 잘림. `color=None`은 깎기.
- `region=` 튜플은 항상 `(x, y, z, w, d, h)` 순서 (z가 셋째!). 순서 실수로 꽃이 0개 나온 적 있음 — stats의 색별 개수로 확인.
- 색은 `m.pal.add(name, hex, emit=..)`로 이름 등록 후 이름으로 사용. 최대 255색. 조명은 `emit>0`.
- 키트 시트처럼 조각이 여러 개면 `with m.part("name"):` 안에서 그린다 → .vox에 조각별 오브젝트로 저장
  (MagicaVoxel에서 따로 이동 가능). 이때 전체 격자는 256을 넘어도 되고, 조각 하나만 256 이하면 된다.
  예: `models/model_1027_2140.py` (player_house를 import해 붙여 넣고 조각 6개 추가).
- 주요 치수는 스크립트 상단 상수(`FLOOR`, `EAVE`, …)로 두고 나머지 좌표를 상수에서 유도할 것.
  비율 수정이 한 줄 수정이 되도록. (리터럴 좌표로 짰다가 깊이 변경 때 전부 고친 적 있음)

## 레퍼런스 재현 요령 (플레이어의 집에서 배운 것)
- 레퍼런스는 대개 **원근 렌더**다. 화면 픽셀로 치수를 재지 말고 **크기를 아는 요소(문 ≈ 21 voxel) 대비 비율**로.
  `VIEW`에 `fov`를 주면 원근 프리뷰가 되고, `fit-camera`가 정사영/원근 중 잘 맞는 쪽을 찾아 준다.
- 카메라를 먼저 맞춘다(`fit-camera`). 그 다음 비율 → 실루엣(점수 이미지의 빨강/파랑) → 색 → 디테일 순.
- 점수는 관찰이지 목표가 아니다: 앞으로 튀어나온 요소가 문·창을 가리면 점수보다 보이는 핵심 요소를 택한다.
- 색 보정: 프리뷰는 정면 ×0.9, 좌측면 ×0.76으로 음영. 레퍼런스에서 샘플한 정면 색 ÷ 0.9 ≈ 기본색.
- 조립 순서: 벽 → `bricks()` 텍스처 → 지붕 → 개구부(깎기) → 장식 → 식물(마지막, `only_empty`).
- 최종 확인은 `--open` 후 `VT shot`으로 MagicaVoxel에 실제로 로드됐는지 본다.
