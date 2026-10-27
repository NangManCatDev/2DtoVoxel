# 모델 스크립트 쓰기

[English](model-scripts.md) | **한국어** · ← [README로 돌아가기](../README.ko.md)

모델 하나는 `models/` 안의 Python 파일 하나입니다. Claude가 이 스크립트를 쓰고 고치며, 직접 고쳐도 됩니다. `.vox`는 항상 스크립트에서 다시 만들어집니다.

## 스크립트에 들어가는 것

| 이름 | 필수 | 의미 |
|---|---|---|
| `NAME` | 예 | 출력 폴더와 파일 이름 |
| `build()` | 예 | `Model`을 반환 |
| `REFERENCE` | 아니오 | 레퍼런스 이미지 경로. 있으면 비교 이미지와 점수가 만들어짐 |
| `VIEW` | 아니오 | 미리보기 카메라. 예: `{"azimuth": 36, "elevation": 18, "fov": 0}`. 방위각 0은 정면을, 90은 왼쪽 면을 봄. `fov`가 0보다 크면 원근 카메라 |
| `SCORE_VIEW` | 아니오 | 점수용 카메라가 `VIEW`와 다를 때 (변환 결과는 정면에서 점수를 매김) |
| `CUTOUT` | 아니오 | 배경 제거 설정. 물체가 여러 개인 시트면 `{"keep": "all"}` |

## 좌표

`x`는 오른쪽, `y`는 안쪽(**`y = 0`이 정면**, MagicaVoxel 기본 카메라가 보는 면), `z`는 위쪽입니다. 박스는 위치와 크기로 지정합니다. `box(x, y, z, w, d, h, 색)`은 `x … x+w-1` 범위 등을 채우고, 격자 밖은 잘려 나갑니다. `region=` 인자는 항상 `(x, y, z, w, d, h)` 순서입니다. 저장되는 오브젝트 하나는 축마다 최대 256 voxel, 색은 최대 255개입니다.

## 예제

```python
from voxtool import Model

NAME = "tiny_hut"
VIEW = {"azimuth": 36, "elevation": 20}


def build() -> Model:
    m = Model(40, 34, 32, seed=1)                  # 격자 크기: x(폭), y(깊이), z(높이)
    m.pal.add("wall", "#dcc3a0"); m.pal.add("wall2", "#d2b893")
    m.pal.add("roof", "#0b8691"); m.pal.add("roof_hi", "#1ba3ad")
    m.pal.add("door", "#8c2b22"); m.pal.add("glass", "#8a8094")
    m.pal.add("lamp", "#ffd84a", emit=4)            # MagicaVoxel Render 탭에서 빛남
    m.pal.add("leaf", "#2c5a19"); m.pal.add("leaf2", "#3d7524")

    m.shell(6, 8, 0, 28, 18, 16, "wall", t=2, top=False)          # 벽, y=8이 정면
    m.bricks(["wall", "wall2"], target="wall", bw=6, bh=3)       # 돌 블록 질감
    roof = (4, 6, 16, 32, 22)                                     # 지붕 바닥 영역 x, y, z, w, d
    m.gable_wall(*roof, "x", "wall", region=(6, 8, 28, 18))       # 지붕 아래 박공벽
    m.gable_roof(*roof, "x", ["roof_hi", "roof"], t=2)            # 용마루는 x 방향, 줄무늬 판자
    m.box(17, 8, 0, 6, 2, 10, "door")                             # 문, 깊이 2
    m.box(9, 8, 6, 5, 1, 5, "glass"); m.box(26, 8, 6, 5, 1, 5, "glass")
    m.box(15, 7, 9, 1, 1, 2, "lamp")                              # 벽 앞의 등
    m.blob(10, 5, 2, 3.5, 2.5, 2.5, ["leaf", "leaf2"])            # 덤불
    m.blob(30, 5, 2, 3.5, 2.5, 2.5, ["leaf", "leaf2"])
    return m
```

`models/tiny_hut.py`로 저장하고 `voxtool build models/tiny_hut.py --open`을 실행하면 이렇게 나옵니다.

![tiny_hut 예제 미리보기](images/example-tiny-hut.png)

코너석, 계단식 박공, 차양, 랜턴, 화단, 덩굴까지 들어간 실제 예시는 [models/player_house.py](../models/player_house.py)를 보세요.

## DSL 레퍼런스

모든 메서드는 `Model`에 있습니다([voxtool/model.py](../voxtool/model.py)). `c`는 팔레트 이름, 팔레트 번호, 또는 `None`(깎기)입니다.

| 분류 | 메서드 | 용도 |
|---|---|---|
| 팔레트 | `m.pal.add(name, hex, emit=0, glass=0, metal=0, rough=0.5)` | 이름 붙은 색 등록. `emit`은 발광, `glass`는 투명, `metal`은 금속 재질 |
| | `m.pal.ramp(name, [hex, ...])` | `name0`, `name1`, … 명암 변형 등록 |
| 기본 도형 | `box(x, y, z, w, d, h, c, only_empty=False, only_filled=False)` | 꽉 찬 박스 (`c=None`이면 깎기) |
| | `carve(x, y, z, w, d, h)` | 박스 영역 비우기 |
| | `shell(x, y, z, w, d, h, c, t=1, top=True, bottom=True)` | 벽 두께 `t`인 속 빈 박스 |
| | `set(x, y, z, c)` / `get(x, y, z)` | 복셀 하나 |
| | `line(p0, p1, c, r=0)` | 3D 선. `r`을 주면 정육면체 붓으로 굵게 |
| | `ellipsoid(cx, cy, cz, rx, ry, rz, c)` | 타원체 |
| | `cylinder(cx, cy, z, r, h, c, axis="z")` | z, x, y 방향 원기둥 |
| | `where(x, y, z, w, d, h, fn, c)` | `fn(X, Y, Z)`(numpy 벡터 연산)가 참인 곳을 채움 — 어떤 모양이든 가능 |
| | `paint_fn(x, y, z, w, d, h, fn)` | 복셀마다 다시 칠하기. `fn`이 팔레트 번호를 반환 |
| 건축 | `gable_roof(x, y, z, w, d, ridge, c, slope=1.0, t=2, fill=None)` | 박공지붕. 색 목록을 주면 단마다 번갈아 칠해 판자·기와 느낌 |
| | `gable_wall(x, y, z, w, d, ridge, c, slope=1.0, region=None)` | 같은 지붕 아래를 정확히 맞춰 채움 (박공벽, 다락) |
| | `shed_roof(x, y, z, w, d, down, c, slope=0.5, t=2)` | 외쪽지붕 / 현관 차양 |
| | `stairs(x, y, z, w, steps, c, rise=1, run=2, direction="-y")` | 일자 계단 |
| 질감·유기물 | `bricks(colors, target, bw=6, bh=3, mortar=None, p=None, region=None)` | 기존 복셀에 엇갈린 돌·벽돌 무늬 |
| | `vary(colors, target, p=None, region=None)` | 무작위로 색을 바꿔 평평한 면에 변화 주기 |
| | `blob(cx, cy, cz, rx, ry, rz, colors, noise=0.35, density=1.0)` | 울퉁불퉁한 타원체: 덤불, 나뭇잎, 바위 |
| | `vine(x, y, z, length, colors, wall="-y", drift=0.35, leaf=0.6, spread=1)` | 벽을 타고 아래로 늘어진 덩굴 |
| | `sprinkle(colors, prob, target, region=None)` | 표면 복셀 일부를 무작위로 다시 칠하기 (덤불 속 꽃) |
| | `scatter_on_top(region, colors, prob, target=None)` | 드러난 윗면 위에 복셀 올리기 |
| 오브젝트·파일 | `with m.part(name): ...` | 블록 안에서 그린 복셀이 `.vox`의 별도 오브젝트가 됨 (키트 시트) |
| | `Model.from_vox(path)` / `m.paste_vox(path, x, y, z)` | 기존 `.vox`(변환 결과나 MagicaVoxel 편집본)에서 시작 / 붙여 넣기 |
| 변형·출력 | `mirror_x(x0, x1)` / `copy(x, y, z, w, d, h, dx, dy, dz)` | 영역 대칭 복사 / 복제 |
| | `stats()` / `save(path)` | 요약(색별 복셀 개수) / `.vox` 저장 (MagicaVoxel에서 저장된 파일은 먼저 백업) |

## 도움이 되는 습관

- 주요 치수는 맨 위 상수(`FLOOR`, `EAVE`, …)로 두고 나머지 좌표를 모두 상수에서 유도하세요. 비율 변경이 한 줄 수정이 됩니다.
- 조립 순서: 벽 → `bricks()` 질감 → 지붕 → 개구부(깎기) → 장식 → 식물(마지막, `only_empty`로).
- `stats()`의 색별 개수를 확인하세요. 0개인 색이 있으면 대개 `region` 순서를 잘못 쓴 것입니다.
