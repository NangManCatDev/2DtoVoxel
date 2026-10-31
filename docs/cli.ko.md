# 명령줄과 설정

[English](cli.md) | **한국어** · ← [README로 돌아가기](../README.ko.md)

프로젝트 폴더에서 실행합니다. `voxtool`은 `pip install -e .` 후에 쓸 수 있고, 아니면 `py -m voxtool`(Windows)이나 `python3 -m voxtool`(macOS / Linux)을 쓰세요.

## 명령

| 명령 | 하는 일 |
|---|---|
| `voxtool build models/<이름>.py [--open] [--no-score] [--res N]` | `output/<이름>/`에 빌드(`.vox`, 미리보기, 비교, 점수). `depth:`와, 있을 때만 `loose:`도 출력([점수가 못 보는 것](how-it-works.ko.md#점수가-못-보는-것)). `--open`은 MagicaVoxel에서 열기. `--res`는 스크립트의 `RES`를 덮어씀(설계는 그대로, 복셀만 더 곱게) |
| `voxtool score models/<이름>.py [--res N] [--zoom 영역]` | `REFERENCE`(와 `EXTRA_REFERENCES`의 그림마다, `views` 아래)와 비교한 점수를 JSON으로 출력. `--zoom top-right`(점수의 3×3 영역 이름)나 `--zoom x0,y0,x1,y1`(레퍼런스 픽셀 좌표)을 주면 대신 레퍼런스 원래 해상도의 확대 비교를 만듦 → `_zoom_<영역>.png` |
| `voxtool fit-camera models/<이름>.py [--fovs 0,25,45] [--ref N]` | 가장 잘 맞는 `VIEW`를 찾고 `_fit.png` 작성. `--ref 1`이면 `EXTRA_REFERENCES`의 첫 그림에 맞춤(→ `_fit_ref1.png`) |
| `voxtool angles models/<이름>.py 30,20 42,15,30` | `az,el[,fov]` 카메라들을 레퍼런스 옆에 렌더 → `_angles.png` |
| `voxtool render <파일.vox> [--az 30 --el 30 --fov 0]` | 아무 `.vox`(MagicaVoxel이 만든 파일 포함)의 미리보기 시트 |
| `voxtool open <파일.vox>` / `voxtool shot` | MagicaVoxel에서 열기 / 창 캡처(Windows) |
| `voxtool ref grid\|crop\|sample\|palette\|cutout <이미지>` | 레퍼런스 분석 도구: 픽셀 격자, 확대 크롭, 지점 색, 주요 색, 배경 제거 |
| `voxtool compare <a.png> <b.png> ...` | 이미지를 나란히 붙이기 |
| `voxtool extrude <이미지> --name N [--depth 4 --inflate]` | 이미지·픽셀아트 → 복셀, Claude 없이 |
| `voxtool carve --front f [--side s --top t] --name N` | 실루엣 → 복셀, Claude 없이 |
| `voxtool sprites <스크립트\|vox> [--dirs 8 --scale 4]` | 스프라이트 시트 + `manifest.json` |
| `voxtool export <스크립트\|vox> --format glb\|obj\|ply` | 메시 내보내기 |
| `voxtool recolor <스크립트\|vox> --swap 이름=#hex \| --hue 30` | 팔레트 변형 |
| `voxtool ui [--port 8765] [--no-browser]` | 웹 UI 실행 |
| `voxtool install-skill [--dest ~/.claude/skills]` | 모든 프로젝트에서 `/voxelize` 쓰기 |

## 출력물

생성된 것은 모두 `output/<이름>/`에 저장되고 언제든 다시 만들 수 있습니다(git 제외 폴더).

| 파일 / 폴더 | 내용 |
|---|---|
| `<이름>.vox` | 모델 |
| `<이름>_iso.png`, `_sheet.png` | 3/4 미리보기, 전체 뷰 |
| `<이름>_turn.png` | 레퍼런스 방향부터 90°씩 돌려 본 네 방향 |
| `<이름>_compare.png`, `_score.png`, `_scores.jsonl` | 레퍼런스 비교, 차이 이미지(레퍼런스마다 한 줄), 점수 기록 |
| `<이름>_angles.png`, `_fit.png`, `_fit_ref<N>.png` | 카메라 각도 비교, 카메라 맞춤 |
| `<이름>_zoom_<영역>.png` | `score --zoom`의 확대 비교, 또는 빌드 뒤 차이가 가장 큰 영역의 확대 |
| `<이름>_edited_<시각>.vox` | MagicaVoxel에서 저장했던 파일의 백업 |
| `sprites/`, `export/`, `variants/` | 스프라이트 시트 + manifest, 메시, 팔레트 변형 |

UI 작업 로그와 빌드별 스냅샷은 `output/_jobs/<id>/`에 있습니다.

## 설정

| 설정 | 방법 |
|---|---|
| Claude Code CLI 위치 | 환경변수 `CLAUDE_CLI` = `claude` 실행 파일의 전체 경로 |
| MagicaVoxel 위치 | 환경변수 `MAGICAVOXEL_EXE` = `MagicaVoxel.exe`(macOS는 `.app`)의 전체 경로 |
| 포트 | `voxtool ui --port 9000` (사용 중이면 다음 빈 포트) |
| 브라우저 자동 열기 끄기 | `voxtool ui --no-browser` |
| UI 언어 | 오른쪽 위 선택 상자. 처음에는 브라우저 언어를 따름 |
| 작업별 상한 | UI의 "최대 비용 (USD)", "최대 빌드 횟수" 칸 |

UI는 `PATH`에 있는 `claude`를 찾고, 없으면 VS Code의 Claude Code 확장에 들어 있는 실행 파일을 찾습니다(VS Code Insiders, Cursor 포함). MagicaVoxel은 흔한 위치에서 자동으로 찾습니다. 바탕화면·다운로드·홈 폴더·`C:\Program Files`·`C:\` 아래의 `MagicaVoxel*` 폴더, macOS는 `/Applications`입니다.
