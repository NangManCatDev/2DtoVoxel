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
| `EXTRA_REFERENCES` | 아니오 | 같은 물체의 다른 그림들. 각각 그 그림이 물체를 본 카메라와 함께. 예: `[("reference/x_side.png", {"azimuth": 90, "elevation": 0})]` (세 번째 항목은 그 그림의 `CUTOUT`). 빌드할 때마다 그림마다 점수를 매김. 도면이면 정면 0, 왼쪽 90, 뒤 180, 오른쪽 270, 위 `"elevation": 90`, 모르면 `voxtool fit-camera ... --ref 1` |
| `RES` | 아니오 | 설계 단위 하나당 복셀 수. `Model(..., res=RES)`로 쓰고, `voxtool build --res N`으로 덮어쓸 수 있음 ([고해상도 모델](#고해상도-모델) 참고) |

## 좌표

`x`는 오른쪽, `y`는 안쪽(**`y = 0`이 정면**, MagicaVoxel 기본 카메라가 보는 면), `z`는 위쪽입니다. 박스는 위치와 크기로 지정합니다. `box(x, y, z, w, d, h, 색)`은 `x … x+w-1` 범위 등을 채우고, 격자 밖은 잘려 나갑니다. `region=` 인자는 항상 `(x, y, z, w, d, h)` 순서입니다. 색은 최대 255개입니다.

`.vox`의 오브젝트 하나는 축마다 최대 256 voxel입니다. 이보다 큰 격자나 부품은 저장할 때 256칸 조각으로 나뉘고 MagicaVoxel 그룹 하나로 묶이므로, 여전히 한 덩어리로 옮길 수 있습니다. MagicaVoxel은 장면을 축마다 약 2048 voxel까지 보여 줍니다.

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

## 고해상도 모델

100 voxel 안팎의 모델보다 더 세밀하게 만들고 싶을 때 세 가지 도구를 함께 씁니다.

1. **`res`: 같은 스크립트, 더 고운 복셀.** 스크립트는 평소처럼 설계 단위로 쓰고, 맨 위에 `RES = 1`을 넣은 뒤 `Model(w, d, h, res=RES)`로 모델을 만듭니다. 좌표는 그대로인데 설계 단위 한 칸이 `RES × RES × RES` 복셀이 되어, 곡면·지붕·덤불이 매끄러워지고 질감이 고와집니다. 반복은 `RES = 1`로 빠르게 하고, `voxtool build models/<name>.py --res 3`으로 최종 해상도를 시험해 본 뒤, 마음에 들면 스크립트의 `RES`를 3으로 바꾸세요(`--res`는 그 빌드에만 적용되므로, 그대로 두면 나중에 다시 빌드할 때 1로 돌아갑니다). `m.v`를 직접 다루는 코드는 복셀 단위이니 그 부분은 `m.res`를 곱해야 합니다.
2. **`paint_reference`: 그림에서 가져오는 색.** 형태가 확정되면 `build()`의 마지막 줄에 `m.paint_reference(REFERENCE, VIEW)`를 넣습니다. 맞춘 카메라와 점수와 같은 정렬로 레퍼런스의 픽셀을 읽어, 그림에 보이는 복셀마다 그 색을 칠합니다. 손으로는 놓을 수 없는 명암, 얼룩, 무늬, 그라데이션이 들어갑니다. 레퍼런스에 보이지 않는 복셀은 원래 색을 유지하고, 발광 색은 건드리지 않으며, 원래 색과 너무 다른 색(`tol`)은 건너뜁니다. 그래서 형태가 조금 어긋난 곳에서도 벽이 앞에 있는 덤불 색을 받지 않습니다. 실루엣이 이미 잘 맞을 때(IoU 0.95 이상) 가장 효과가 좋고, 덜 맞으면 얼룩져 보입니다.
3. **`score --zoom`: 세부를 원래 크기로 확인.** 점수는 320 px로 줄여서 비교하므로 작은 것은 보이지 않습니다. `voxtool score models/<name>.py --zoom top-right`(점수의 `worst:` 목록에 나온 영역 이름, 또는 `ref grid`로 읽은 레퍼런스 픽셀 좌표 `x0,y0,x1,y1`)는 그 영역의 레퍼런스, 빌드, 차이를 레퍼런스 원래 해상도로 보여 줍니다.

실제 모델 두 개에 `paint_reference`를 적용한 결과입니다.

| 모델 | 실루엣 일치(IoU) | 색 차이(ΔE) 전 → 후 |
|---|---|---|
| UI에서 만든 포장석 바닥 | 0.969 | 5.2 → 2.3 |
| 손으로 쓴 플레이어의 집 | 0.899 | 20.0 → 18.3 (형태가 더 어긋나 있어 `tol`이 대부분의 색을 유지함) |

플레이어의 집을 `--res 1`, `2`, `3`으로 빌드한 모습입니다(복셀 12만 5천, 100만, 340만 개). 형태는 그대로이고 덤불과 질감만 고와집니다.

![res 1, 2, 3으로 빌드한 플레이어의 집](images/res.jpg)

### 나무, 덤불 같은 식물

복셀 아트의 잎은 "덩어리의 덩어리"입니다. 정육면체 몇 개짜리 작은 잎 뭉치가 모여 덩어리가 되고, 덩어리가 모여 수관이 되며, 그 사이에 어두운 틈이 있습니다. `ellipsoid`나 `blob` 같은 기본 도형으로는 매끈한 공이 되므로, 식물용 도구를 따로 씁니다.

- `tube(points, radius, c)`: 점들을 지나는 곡선을 따라 가늘어지는 줄기·가지·뿌리. 색 목록을 주면 나무껍질 줄무늬가 됩니다.
- `foliage(lobes, colors)`: 레퍼런스 외곽선에서 잰 잎 덩어리 `(cx, cy, cz, r)` 위에 수관을 만듭니다. 덩어리마다 작은 덩어리를, 작은 덩어리마다 잎 뭉치(`clump`, 복셀 단위)를 붙이고, 위쪽과 바깥쪽은 밝게, 틈에는 어두운 속이 보이게 칠합니다. 줄기와 가지를 먼저 그리면 잎이 그 주위로 자랍니다.
- `tree(x, y, z, height, leaves, bark, style=...)`: 줄기, 뿌리, 잎 덩어리마다 뻗는 가지, `foliage` 수관을 한 번에 만듭니다. `lobes=`를 직접 주거나 스타일로 배치합니다.

![여섯 가지 나무 스타일](images/trees.jpg)

- `crown_depth(lobes, x, y, VIEW)`: 그림에서 잰 잎 덩어리는 모두 한 평면, 즉 `(x, y)`의 줄기를 지나 카메라를 향한 수직 평면 위에 있습니다. 그래서 정면에서는 맞지만 옆에서 보면 납작합니다. 이 함수는 맞닿은 덩어리 무리마다 `VIEW`에서 본 외곽이 측정한 외곽과 같은 똑바로 선 타원체를 잡고(외곽선이 허락하면 위에서 볼 때 둥글게), 그 안에서 각 덩어리의 시선 방향을 따라 복사본을 더합니다. 그래서 레퍼런스 방향의 외곽선은 그대로입니다. `tree(..., lobes=..., view=VIEW)`가 대신 해 줍니다. 외곽선의 빈 곳을 카메라를 향한 평면에 복셀 한 겹으로 채우거나, 덩어리를 시선 방향으로 복사하지 마세요. 정면 점수는 조금 오르지만 다른 방향에서 보면 기울어진 판이 됩니다.
- `carve_to_reference(REFERENCE, VIEW, only=잎들)`: 레퍼런스의 배경에 떨어지는 복셀을 깎아, 잎 덩어리로는 대략만 맞는 자연물 외곽을 정리합니다. 먼저 모델 외곽을 레퍼런스 높이에 맞춰 놓고 깎으므로 비율을 먼저 맞춘 뒤 쓰고, `only`로 범위를 정해 줄기나 받침은 건드리지 않게 하세요.

키 큰 나무 5그루 시트에서, 잎 덩어리와 줄기의 측정값은 그대로 두고 손으로 쓴 잎 뭉치 코드만 이 도구로 바꿨을 때의 결과입니다.

| 버전 | IoU | ΔE |
|---|---|---|
| 직접 쓴 잎 뭉치 코드 (Claude가 처음 쓴 스크립트) | 0.847 | 15.2 |
| `tube` + `foliage` | 0.844 | 14.6 |
| … + `carve_to_reference(only=잎)` | 0.869 | 14.5 |
| … + `paint_reference` | 0.869 | 10.7 |

퍼진 나무 5그루 시트에서 Claude가 처음 쓴 스크립트는 외곽선을 줄기 평면의 복셀 한 겹으로 채우고 잎 덩어리를 시선 방향으로 복사했습니다. 정면 점수는 IoU 0.914였지만 옆에서 보면 수관이 모두 기울어진 판이었습니다. 같은 측정값으로 `crown_depth`, `foliage`, `tube`를 써서 다시 만들자 수관이 어느 방향에서나 둥글어졌고, 정면 점수는 0.842였습니다. 점수는 한 방향에서만 재므로 빌드마다 `_turn.png`의 옆·뒤 모습과 `depth:` 줄을 꼭 확인하세요. 처음 스크립트 같은 수관에는 `(thin)`이 붙습니다.

레퍼런스 자체가 복셀 그림이면 그 칸 크기에 맞추세요. 레퍼런스의 정육면체 하나가 복셀 하나가 되게 합니다. 같은 나무를 `--res 2`로 만들면 잎이 그림보다 잘게 쪼개져 점수가 더 낮았습니다(IoU 0.855, ΔE 13.3).

플레이어의 집에 `score --zoom bottom-right`를 쓰면 전체 점수로는 보이지 않는 것이 드러납니다. 레퍼런스의 덤불은 화단 밖으로 흘러넘치고 화단 앞면에 금이 가 있는데, 빌드는 가지런한 생울타리에 지그재그 홈입니다.

![화단 확대 비교: 레퍼런스, 빌드, 차이](images/zoom.jpg)

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
| 식물 | `tube(points, radius, c, smooth=True)` | 휘고 가늘어지는 줄기·가지·뿌리. 색 목록이면 나무껍질 줄무늬 |
| | `foliage(lobes, colors, clump=1.8, density=1.0, core=None, tips=None)` | 잎 덩어리 `(cx, cy, cz, r)` 위의 울퉁불퉁한 수관. 색은 어두운 것 → 밝은 것 |
| | `crown_depth(lobes, x, y, view, fill=1.0)` | 그림에서 잰 잎 덩어리를 수관 깊이 방향으로 채우기 |
| | `tree(x, y, z, height, leaves, bark, style="round", width=None, lobes=None, view=None, ...)` | 나무 한 그루. 스타일 `round`, `column`, `cone`, `tiered`, `branched`, `spread`. 잰 `lobes`에는 `view`도 |
| 레퍼런스 맞춤 | `carve_to_reference(reference, view, only=None, margin=0.5, cutout=None)` | 레퍼런스 배경에 떨어지는 복셀 깎기 |
| 떨어진 조각 | `loose_pieces()` / `remove_loose(max_voxels=8)` | 자기 물체의 나머지와 닿지 않은 조각(빌드의 `loose:` 줄이 보여 주는 것) / 그중 설계 단위 `max_voxels`칸 이하 지우기(`None`이면 전부). `paint_reference`보다 먼저 호출 |
| 파손 | `damage(level=1.0, seed=0, debris=0.35, scorch=True)` | 부서진 변형: 깨진 모서리, 구멍, 금, level 3이면 무너진 윗부분. 떨어져 나간 조각은 잔해로 떨어짐 |
| 레퍼런스 색 | `paint_reference(reference, view, colors=96, tol=30, only=None, blend=1.0, cutout=None)` | 레퍼런스에 보이는 복셀을 그 픽셀 색으로 칠하기(마지막에 호출). 새 색 이름은 `<색>_r1`, … |
| 모델 | `Model(w, d, h, seed=0, res=1)` | 설계 단위 격자. 단위당 `res` 복셀 (`m.res`, `m.dims`. `m.size`는 복셀 격자 크기) |
| 오브젝트·파일 | `with m.part(name): ...` | 블록 안에서 그린 복셀이 `.vox`의 별도 오브젝트가 됨 (키트 시트) |
| | `Model.from_vox(path, res=1)` / `m.paste_vox(path, x, y, z)` | 기존 `.vox`(변환 결과나 MagicaVoxel 편집본)에서 시작 / 붙여 넣기 |
| 변형·출력 | `mirror_x(x0, x1)` / `copy(x, y, z, w, d, h, dx, dy, dz)` | 영역 대칭 복사 / 복제 |
| | `stats()` / `save(path)` | 요약(색별 복셀 개수) / `.vox` 저장 (MagicaVoxel에서 저장된 파일은 먼저 백업) |

## 도움이 되는 습관

- 주요 치수는 맨 위 상수(`FLOOR`, `EAVE`, …)로 두고 나머지 좌표를 모두 상수에서 유도하세요. 비율 변경이 한 줄 수정이 됩니다.
- 조립 순서: 벽 → `bricks()` 질감 → 지붕 → 개구부(깎기) → 장식 → 식물(마지막, `only_empty`로).
- `stats()`의 색별 개수를 확인하세요. 0개인 색이 있으면 대개 `region` 순서를 잘못 쓴 것입니다.
