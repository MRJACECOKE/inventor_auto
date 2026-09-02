# 명세서 — L자 코스 파트 (corner_line)

> 형식: 파트별 정식 명세. 범위: `l_course_big`, `l_course_small`,
> `l_corridor_course`, `l_corridor_course_ver2`. **`l_course_combined` 제외.**
> 단위: mm. Inventor 2027.1. 전 파트 검증 결과 **PASS**.

---

## 0. 공통 규약

| 항목 | 값 |
|---|---|
| 소스 이미지 | `IMG-001` = `corner_line/90_degree_corner_1.jpg`, `IMG-002` = `corner_line/90_degree_corner_2.jpg` |
| 원점 / 데이텀 | O = L자 바깥(볼록) 코너, 바닥면. +X = leg B, +Y = leg A, +Z = 위 |
| 1차 평면 | XY |
| 스키마 | `schemas/measurement.schema.json`, `schemas/cad-feature-plan.schema.json` |
| 피처 구성 | 8 피처 (base_extrude ×1, extrude_add ×5, extrude_cut ×2) — 상세는 엔지니어링 문서 §5 |
| 파생값 | `strip_width = lane_width + 2·wall_thickness`, `inner_off = lane_width + wall_thickness` |
| 유효 조건 | `strip_width < seg_a_length` 및 `< seg_b_length`; `floor_thickness < wall_height` |
| 수용 기준 | 파일 존재 · `.ipt` · size>0 · `kPartDocumentObject` · 솔리드 바디 ≥ 1 · 건강하지 않은 피처 0 · RangeBox == (seg_b × seg_a × wall_height) · Volume == 해석식 |

---

## 1. `l_course_big` — 큰 L자 통로 (사진 1)

### 1.1 정체성

| | |
|---|---|
| 파트명 | `l_course_big` |
| `.ipt` | `output/l_course_big/l_course_big.ipt` (207,872 bytes) |
| 주 소스 이미지 | **IMG-001** (`90_degree_corner_1.jpg`) — 넓은 실내 전경, 검은 패널 벽이 깊게 이어지다 90° 외부 코너로 꺾임 |
| 측정 파일 | `input/l_course_big/measurement-input.json` |
| provenance sha256 | `39de4697f2566b861279b3754734d067eb0c140aaca0d4a8f8e1b9f81ecd3561` |
| 빌드 시각 | 2026-09-01 19:08:42Z |

### 1.2 측정 입력 → 파라미터 맵

| M-ID | 이름 | 값 (mm) | → p_이름 | 사진 근거 / 산출 |
|---|---|---|---|---|
| M001 | `seg_a_length` | 10670 | `p_seg_a_length` | 내측 코너 기준 leg1 5220 + 안목 폭 5450 |
| M002 | `seg_b_length` | 10450 | `p_seg_b_length` | 내측 코너 기준 leg2 5000 + 안목 폭 5450 |
| M003 | `lane_width` | 5450 | `p_lane_width` | 큰 L 통로 안목 폭 (현장 실측) |
| M004 | `wall_thickness` | 150 | `p_wall_thickness` | 격실 벽, 공칭 |
| M005 | `wall_height` | 4700 | `p_wall_height` | 바닥→천장 (현장 실측) |
| M006 | `floor_thickness` | 50 | `p_floor_thickness` | 시뮬값 |
| D001 | `strip_width` | 5750 | `p_strip_width` | `5450 + 2·150` |
| D002 | `inner_off` | 5600 | `p_inner_off` | `5450 + 150` |

### 1.3 기하 (검증됨)

| | |
|---|---|
| 바운딩박스 | 10450 × 10670 × 4700 mm, MinPoint (0,0,0) |
| 체적 | 25,860,025,000 mm³ (해석식과 mm³ 일치) |
| 채움률 | 4.9 % (속 빈 L 복도) |
| 솔리드 바디 | 1 · 피처 8 · 건강하지 않은 피처 0 |
| 검은 패널 벽 | 모델의 **내벽** (오목 모서리, X=5600 / Y=5600 안쪽면) |
| 개방단 | leg A (Y=10670), leg B (X=10450) |

### 1.4 결과

**PASS** — `output/l_course_big/build-report.md`, `validation-report.json`, `preview_iso.png`.

---

## 2. `l_course_small` — 작은 대칭 L자 통로 (사진 2)

### 2.1 정체성

| | |
|---|---|
| 파트명 | `l_course_small` |
| `.ipt` | `output/l_course_small/l_course_small.ipt` (193,536 bytes) |
| 주 소스 이미지 | **IMG-002** (`90_degree_corner_2.jpg`) — 같은 검은 벽 코너 근접, 유리문 쪽으로 갈라지는 좁은 L자 분기 |
| 측정 파일 | `input/l_course_small/measurement-input.json` |
| provenance sha256 | `265820fccfd764c047295e5634f75cdfbb83ebe4281620f7d2e690fe9beda7db` |
| 빌드 시각 | 2026-09-01 19:11:16Z |

### 2.2 측정 입력 → 파라미터 맵

| M-ID | 이름 | 값 (mm) | → p_이름 | 사진 근거 / 산출 |
|---|---|---|---|---|
| M001 | `seg_a_length` | 3950 | `p_seg_a_length` | 내측 코너 기준 leg 1520 + 안목 폭 2430 |
| M002 | `seg_b_length` | 3950 | `p_seg_b_length` | 대칭 — leg 1520 + 2430 |
| M003 | `lane_width` | 2430 | `p_lane_width` | 작은 L 통로 안목 폭 (현장 실측) |
| M004 | `wall_thickness` | 150 | `p_wall_thickness` | 격실 벽, 공칭 (큰 L과 동일) |
| M005 | `wall_height` | 4700 | `p_wall_height` | 바닥→천장 |
| M006 | `floor_thickness` | 50 | `p_floor_thickness` | 시뮬값 |
| D001 | `strip_width` | 2730 | `p_strip_width` | `2430 + 2·150` |
| D002 | `inner_off` | 2580 | `p_inner_off` | `2430 + 150` |

### 2.3 기하 (검증됨)

| | |
|---|---|
| 바운딩박스 | 3950 × 3950 × 4700 mm, MinPoint (0,0,0) |
| 체적 | 7,917,855,000 mm³ (해석식과 mm³ 일치) |
| 채움률 | 10.8 % |
| 솔리드 바디 | 1 · 피처 8 · 건강하지 않은 피처 0 |
| 대칭 | leg A == leg B (기하상 45° 평면 대칭이나 원점평면 아니므로 미선언) |
| 개방단 | leg A (Y=3950), leg B (X=3950) |

### 2.4 결과

**PASS** — `output/l_course_small/build-report.md`, `validation-report.json`, `preview_iso.png`.

---

## 3. `l_corridor_course` — 파이프라인 프루프 (참조)

### 3.1 정체성

| | |
|---|---|
| 파트명 | `l_corridor_course` |
| `.ipt` | `output/l_corridor_course/l_corridor_course.ipt` |
| 소스 이미지 | IMG-001 + IMG-002 (구조 참조). **치수는 임의** — 사진에서 유도하지 않음 |
| 측정 파일 | `input/wall_panel_corner_module/measurement-input.json` (폴더명은 옛 가설 유래) |
| provenance sha256 | `551a64378b6a5666b27fbe810007bb7cc63e4b44a888e80bc4383d6e8dab52e4` |
| 빌드 시각 | 2026-09-01 18:09:54Z |
| 목적 | 8-피처 원점정렬 L자 구성법을 Inventor COM에서 처음으로 관통 검증 (E2E 프루프) |

### 3.2 파라미터 맵

| M-ID | 이름 | 값 (mm) | 비고 |
|---|---|---|---|
| M001 | `seg_a_length` | 2430 | 임의 (데이텀 변환 없음) |
| M002 | `seg_b_length` | 5755 | 임의 |
| M003 | `lane_width` | 1000 | 임의 (작은 주행폭) |
| M004 | `wall_thickness` | 100 | 공칭 |
| M005 | `wall_height` | 4700 | 사진 계열 천장고 |
| M006 | `floor_thickness` | 50 | 시뮬값 |
| D001 | `strip_width` | 1200 | `1000 + 2·100` |
| D002 | `inner_off` | 1100 | `1000 + 100` |

### 3.3 기하 (검증됨)

바운딩박스 5755 × 2430 × 4700 mm · 체적 6,915,150,000 mm³ · 채움률 10.5 % ·
1 바디 · 8 피처 · **PASS**.

### 3.4 상태

**참조 / 회귀 픽스처.** `l_course_big` / `l_course_small` 로 대체됨. 삭제 금지 (구성법 검증 근거).

---

## 4. `l_corridor_course_ver2` — 스냅샷 (참조)

### 4.1 정체성

| | |
|---|---|
| 파트명 | `l_corridor_course_ver2` |
| `.ipt` | `output/l_corridor_course_ver2/l_corridor_course_ver2.ipt` (204,800 bytes) |
| 소스 이미지 | IMG-001 + IMG-002 (구조 참조) |
| 측정 파일 | `input/l_corridor_course_ver2/measurement-input.json` |
| provenance sha256 | `ff77a802c66b4257c8b34c6bef3782a336bcbc214b3dace814486d318bea076e` |
| 빌드 시각 | 2026-09-01 18:25:34Z |
| 목적 | 사용자 요청에 따른 이름 지정 스냅샷. `lane_width` 1000 유지, `l_corridor_course` 와 형상 완전 동일 |

### 4.2 파라미터 맵

`l_corridor_course` 와 동일: seg_a 2430 · seg_b 5755 · lane 1000 · wall_t 100 ·
wall_h 4700 · floor_t 50 · strip_width 1200 · inner_off 1100.

### 4.3 기하 (검증됨)

바운딩박스 5755 × 2430 × 4700 mm · 체적 6,915,150,000 mm³ · 채움률 10.5 % ·
1 바디 · 8 피처 · **PASS**. (`l_corridor_course` 와 수치 동일.)

### 4.4 상태

**참조 스냅샷.** 후속 치수 변경 시 `input/l_corridor_course_ver2/measurement-input.json`
에서 수정 후 재빌드.

---

## 5. 파트 간 비교표

| 항목 | l_course_big | l_course_small | l_corridor_course | l_corridor_course_ver2 |
|---|---|---|---|---|
| 주 소스 사진 | IMG-001 | IMG-002 | (구조 참조) | (구조 참조) |
| lane_width | 5450 | 2430 | 1000 | 1000 |
| seg_a_length | 10670 | 3950 | 2430 | 2430 |
| seg_b_length | 10450 | 3950 | 5755 | 5755 |
| wall_thickness | 150 | 150 | 100 | 100 |
| wall_height | 4700 | 4700 | 4700 | 4700 |
| floor_thickness | 50 | 50 | 50 | 50 |
| bbox X·Y·Z (mm) | 10450·10670·4700 | 3950·3950·4700 | 5755·2430·4700 | 5755·2430·4700 |
| 체적 (mm³) | 25,860,025,000 | 7,917,855,000 | 6,915,150,000 | 6,915,150,000 |
| 채움률 | 4.9 % | 10.8 % | 10.5 % | 10.5 % |
| 결과 | PASS | PASS | PASS | PASS |
| 상태 | 최종 | 최종 | 참조 | 참조 |

---

## 6. 공통 미포함 사항

엔드 캡 · 램프 · 필렛/모따기 · 패널 분할선 · 초록 띠 · 걸레받이 · 밝은 코너 스트립 ·
표면 텍스처. 벽/바닥 두께는 실측 불가로 공칭·시뮬값. 재질은 메타(`concrete`)만.

---

## 7. 변경 이력 요약

| 순서 | 사건 | 비고 |
|---|---|---|
| 1 | 초기 가설 "벽 패널 코너 모듈" | 박스로 산출 → 폐기. 폴더명 `wall_panel_corner_module` 만 잔존 |
| 2 | L자 단면 압출 재설계 | 여전히 박스+홈 → 폐기 |
| 3 | 목적 확정: Isaac Sim L자 코리도 (내·외벽 포함) | `l_corridor_course` E2E 프루프 (lane 1000) |
| 4 | 스냅샷 요청 | `l_corridor_course_ver2` |
| 5 | 사진 매핑 확정: IMG-001=큰 L, IMG-002=작은 L, 다리 길이 = 내측 코너 기준 | `l_course_big`, `l_course_small` |
| 6 | 합친 버전 | `l_course_combined` (**본 명세 범위 밖**) |
