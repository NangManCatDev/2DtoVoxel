---
name: voxelize
description: >-
  Turn a reference image (reference/*.png) into a MagicaVoxel .vox model: study the image, write a
  build script in models/, iterate against the reference using measured scores (silhouette IoU,
  colour ΔE) and preview renders, then open it in MagicaVoxel. Also covers quick no-LLM conversion
  of pixel art (extrude/carve) and game-asset outputs (sprite sheets, OBJ/GLB/PLY, palette variants).
  Use when the user drops in a reference image or asks for a voxel model, e.g. "make a voxel model of
  reference/x.png", "turn this into MagicaVoxel", "voxelize", "복셀로 만들어줘", "매지카복셀 모델로",
  "이 그림 복셀로", "스프라이트 시트 뽑아줘".
---

# voxelize — 레퍼런스 이미지 → MagicaVoxel 모델

인자: 레퍼런스 이미지 경로 (예: `reference/플레이어의집_레퍼런스.png`). 없으면 `reference/`에서 가장 최근 이미지를
쓰고, 어떤 걸 골랐는지 말한다. 프로젝트 `CLAUDE.md`의 좌표 규칙과 요령을 따른다.

**필요한 것:** Python 3.10+와 numpy·Pillow·scipy(`pip install -e .`). MagicaVoxel 0.99.x는 열기·캡처에만
필요하고, 창 캡처(`shot`)는 Windows 전용이다.

**명령 형식:** 아래 `VT`는 voxtool 실행 명령이다 — Windows `py -m voxtool`, macOS/Linux `python3 -m voxtool`,
설치했다면 `voxtool`. UI가 실행한 작업이면 지시문에 적힌 형식을 정확히 그대로 쓴다(권한 규칙과 일치해야 함).

## 작업 → 명령 (먼저 여기서 고른다)

| 요청 | 길 |
|---|---|
| 그림을 정교한 복셀 모델로 | 아래 1~5단계 (스크립트 작성 + 점수 기반 반복) |
| 더 세밀하게 / 고해상도로 | 기존 스크립트에 `RES` 적용 → 4단계 (`paint_reference`, `--res`, `--zoom`) |
| 픽셀아트·아이콘을 바로 두께 있는 복셀로 | `VT extrude <img> --name N [--depth 4 --inflate]` → 필요하면 2단계부터 다듬기 |
| 정면/측면/윗면 그림 여러 장 | `VT carve --front f --side s --top t --name N` → 다듬기 |
| 기존 모델 수정 | 스크립트 수정 → `VT build models/N.py` → 3단계 반복 |
| 게임 에셋 | `VT sprites models/N.py --dirs 8`, `VT export models/N.py --format glb\|obj\|ply`, `VT recolor ...` |

## 1. 관찰 (코드 쓰기 전에)
1. 이미지를 직접 본다(Read).
2. `VT ref cutout <img>` → 배경이 제대로 지워졌는지 확인(점수 계산의 기준이 된다). 물체가 여러 개인 키트
   시트면 `--keep all`, 그리고 스크립트에 `CUTOUT = {"keep": "all"}`.
3. `VT ref grid <img>`로 좌표를 읽고, `VT ref crop <img> x0 y0 x1 y1 --zoom 3`으로 영역별로 확대한다.
4. `VT ref palette <img>`, `VT ref sample <img> x,y x,y ...`로 재질별 실제 색을 얻는다.
5. 구성요소 목록: 본체, 지붕, 개구부, 장식, 조명, 식물, 바닥/계단. 보이지 않는 면은 보이는 면에 맞춰 단순히.
6. 스케일: 크기를 아는 요소 하나(보통 문 ≈ 20 voxel)를 기준으로 비율 환산. 설계는 보통 100 안팎으로 잡는다
   (세밀함은 마지막에 `RES`로 올린다. 축별 256을 넘는 격자는 저장할 때 자동으로 조각 나뉨).

## 2. 빌드 스크립트 — `models/<english_slug>.py`
- docstring에 레이아웃 요약. `NAME`, `REFERENCE`, `VIEW = {"azimuth", "elevation", "fov"}`, `build() -> Model`.
- 맨 위에 `RES = 1`을 두고 `Model(W, D, H, seed=..., res=RES)`로 만든다. 좌표는 전부 설계 단위로 쓰고, `m.v`를
  직접 다루는 헬퍼만 복셀 단위(`m.res`를 곱함)라는 점에 주의. 그래야 4단계에서 해상도를 올릴 수 있다.
- 주요 치수는 상단 상수로, 좌표는 상수에서 유도. 반복 요소는 함수로. 색은 이름으로 등록(기본색 ≈ 정면 샘플 ÷ 0.9).
- 조각이 여러 개면 `with m.part("name"):`. 변환 결과를 바탕으로 쓸 때는 `Model.from_vox(...)`/`m.paste_vox(...)`.
- 참고 예시: `models/player_house.py`.
- 첫 빌드 뒤 `VT fit-camera models/<slug>.py`로 카메라를 맞추고 출력된 `VIEW = {...}`를 스크립트에 넣는다.

## 3. 반복 (보통 4~6회) — 점수와 이미지를 함께 본다
1. `VT build models/<slug>.py` → 출력의 `score: iou=… dE=… worst: …` 를 읽는다.
   - iou = 레퍼런스와 실루엣 겹침(1이 완벽), dE = 색 차이(낮을수록 좋음), worst = 가장 어긋난 영역.
2. `output/<slug>/<slug>_score.png`(빨강 = 빠짐, 파랑 = 넘침), `_compare.png`, `_sheet.png`를 Read로 본다.
3. 우선순위대로 고친다: 카메라 → 전체 비율 → 실루엣(빨강/파랑 영역) → 색 → 디테일. 한 번에 고치고 다시 빌드.
4. stats의 색별 개수로 빠진 요소 확인(0개면 버그).
5. 세부는 320 px 점수로는 안 보인다. `VT score models/<slug>.py --zoom <worst 영역>`(예: `top-right`, 또는
   `ref grid`로 읽은 `x0,y0,x1,y1`)으로 그 영역을 레퍼런스 원래 해상도로 확대해 보고 고친다.

**멈춤 기준 (게이트):**
- 점수가 두 번 연속 오르지 않으면 반복을 멈추고, 남은 차이를 보고한다.
- 점수는 "관찰"이다. 원근 레퍼런스와 정사영 렌더의 차이처럼 점수로는 줄일 수 없는 차이가 있다 —
  그럴 때는 숫자를 억지로 올리지 말고 보이는 핵심 요소(문·창 등)가 가려지지 않는 쪽을 택한다.
- 레퍼런스가 없거나 cutout이 비면 점수는 "확인 불가"로 두고 이미지 비교만으로 진행했다고 밝힌다.

## 4. 고해상도 마무리 (형태가 잘 맞을 때, 또는 세밀함을 요청받았을 때)
반복은 `RES = 1`로 빠르게 하고, 이 단계는 형태가 확정된 뒤 한두 번만 한다(고해상도로는 비율이 고쳐지지 않는다).
1. `build()`의 마지막 줄(`return m` 앞)에 `m.paint_reference(REFERENCE, VIEW)` — 레퍼런스에 보이는 복셀을 그 픽셀 색으로
   칠한다(명암·얼룩·무늬). `VIEW`는 fit-camera로 맞춘 카메라여야 한다(`SCORE_VIEW`가 있으면 그것). IoU 0.95 이상일 때
   효과가 좋고, 덜 맞으면 얼룩진다. 재질 사이 번짐은 `tol`(기본 30)이 막는다. 특정 재질만 칠하려면 `only=[...]`.
2. `VT build models/<slug>.py --res 2`(또는 3)로 같은 스크립트를 더 고운 복셀로 시험한다. 복셀이 수백만 개면 빌드에
   수십 초 걸린다. 결과가 좋으면 스크립트의 `RES`를 그 값으로 바꾸고 한 번 더 빌드한다 — `--res`는 그 빌드에만
   적용되므로, 그대로 두면 나중에 다시 빌드할 때(UI의 Rebuild 포함) 1배로 돌아간다.
3. dE가 줄었는지, `--zoom`으로 핵심 영역이 나아졌는지 확인한다. 나빠졌으면 paint 줄을 빼거나 `only`/`tol`을 조정한다.
   UI 작업이면 이 빌드들도 빌드 횟수에 들어간다.

## 5. 마무리
1. (대화형일 때만) `VT build models/<slug>.py --open` → MagicaVoxel에서 열고, Windows면 `VT shot`으로 로드 확인.
2. 보고: .vox 경로, 최종 점수(iou/dE)와 처음 대비 변화, 비교 이미지, 의도적 타협, Render 탭에서 조명이 빛난다는 점.

## 하지 말 것
- 다른 모델을 빌드하지 않는다 — 그 모델의 .vox(사용자의 MagicaVoxel 편집이 있을 수 있음)를 덮어쓴다.
  (빌드는 MagicaVoxel에서 저장된 파일을 `_edited_<시각>.vox`로 백업하지만, 기대지 말 것.)
- 공용 라이브러리(`voxtool/`), `CLAUDE.md`, `.claude/`를 작업 중에 고치지 않는다. 필요한 기능은 모델 스크립트 안에.
- 점수를 올리려고 레퍼런스에 없는 형태를 만들거나 렌더/점수 코드를 우회하지 않는다.
- `python -c` 같은 임시 코드로 파이프라인 단계를 대신하지 않는다. voxtool 명령으로 안 되는 일이면 보고한다.
