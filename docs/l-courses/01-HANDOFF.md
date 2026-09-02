# 인수인계 문서 — L자 코스 (corner_line)

> 대상: `corner_line/` 사진에서 만든 Isaac Sim용 L자 통로 CAD 일체.
> 범위: `l_course_combined` 는 **제외** (요청에 따라).
> 작성 기준일: 2026-09-01 · Inventor 2027.1 (build 31.1) · 검증 전부 PASS.

---

## 1. 한 줄 요약

`corner_line/` 의 사진 2장(90° 코너 실내)을 **구조 참조**로만 쓰고, 사용자가 현장에서 잰
실측치(폭·길이·높이)를 단일 진실원천(SSOT)으로 삼아, **속 빈 L자 복도**(바닥 슬래브 +
내·외벽, 양 끝 개방)를 파라메트릭 `.ipt` 로 생성했다. Isaac Sim 씬에 바로 임포트 가능.

---

## 1.1 전체 흐름 (플로우 다이어그램)

작업은 항상 아래 9단계(Phase A–I)를 따른다. **E(검증)는 하드 게이트**로, 클린 통과 전에는
Inventor가 실행되지 않는다. 검증 실패 시 사용자 실측 수정으로(빨강 점선), 빌드·형상 검증
실패 시 피처 계획으로(주황 점선) 되돌아간다. 단계별 상세는 엔지니어링 문서 §2·§2.1 참조.

[[FLOW_DIAGRAM]]

- **A–C** (Claude): 사진에서 구조만 분석하고, 채워야 할 실측 항목 목록(`measurement-request.json`)과 파라미터 매핑(`feature-intent.json`)을 생성.
- **D** (사용자): 현장 실측값 입력 → `measurement-input.json`.
- **E–I** (스크립트): 검증 → 결정론적 피처 계획 → Inventor COM 빌드 → `.ipt` 재검증 → 리포트.

---

## 2. 어떤 사진으로 무엇을 만들었나 (핵심)

| 사진 | 사진이 보여주는 것 | 만든 산출물 | 사진에서 얻은 값 (구조/치수 근거) |
|---|---|---|---|
| **`90_degree_corner_1.jpg`** | 넓은 실내 전경. 무광 검은 패널 벽이 오른쪽을 따라 깊게 이어지다 90° 외부 코너로 꺾임. 개방된 쇼룸 바닥, 천장고 ≈ 4.7 m. → **큰 L자 통로** | **`l_course_big.ipt`** (주력). 파이프라인 검증용 초기본 `l_corridor_course` / `l_corridor_course_ver2` 도 이 사진 계열에서 시작 | 큰 L 안목 폭 **5450**; leg1 **5220**, leg2 **5000** (둘 다 검은 벽 안쪽 꼭짓점 기준); 천장고 **4700** |
| **`90_degree_corner_2.jpg`** | 같은 검은 벽 코너를 근접 촬영. 유리문 쪽으로 갈라지는 **작고 좁은 L자 분기** | **`l_course_small.ipt`** | 작은 L 안목 폭 **2430**; 양쪽 다리 **1520** (내측 꼭짓점 기준, 대칭); 천장고 **4700** |
| 두 사진 공통 | 90° 코너, 바닥→천장 ≈ 4700 mm, 벽은 격실(파티션) 구조라 두께 정밀 측정 불가 → 공칭값 사용 | 전체 | 벽 두께 공칭 100 mm(초기본) / **150 mm**(큰·작은 L), 바닥 슬래브 50 mm(시뮬값) |

> **원칙:** 사진에서는 밀리미터/도(度)를 절대 읽지 않는다. 사진은 위상·코너·대칭 등
> **구조만** 제공하고, 모든 실제 길이는 `measurement-input.json` 에서 온다.
> 자세한 이미지 매핑은 `corner_line/annotated_corner_1.png`, `annotated_corner_2.png`,
> `plan_v4.png` 참조.

---

## 3. 산출물 목록 (l_course_combined 제외)

| 파트 | 상태 | 용도 | `.ipt` 경로 |
|---|---|---|---|
| `l_course_big` | **최종** | 사진 1의 큰 L자 통로 | `output/l_course_big/l_course_big.ipt` |
| `l_course_small` | **최종** | 사진 2의 작은 대칭 L자 통로 | `output/l_course_small/l_course_small.ipt` |
| `l_corridor_course` | 참조/회귀 | 8-피처 원점정렬 구성법을 Inventor에서 처음으로 관통 검증한 프루프. 치수는 임의(작은 lane) | `output/l_corridor_course/l_corridor_course.ipt` |
| `l_corridor_course_ver2` | 참조 | 사용자 요청 스냅샷. `l_corridor_course` 와 형상 완전 동일(lane 1000 유지) | `output/l_corridor_course_ver2/l_corridor_course_ver2.ipt` |

각 파트 폴더에는 `cad-plan.json`/`.md`, `build-report.md`, `build-log.txt`,
`validation-report.json`, `preview_iso.png` 가 함께 있다.

### 3.1 검증된 형상 수치

| 파트 | 바운딩박스 (mm, X·Y·Z) | 체적 (mm³) | 채움률 | 바디 | 피처 | 결과 |
|---|---|---|---|---|---|---|
| `l_course_big` | 10450 × 10670 × 4700 | 25,860,025,000 | 4.9 % | 1 | 8 | PASS |
| `l_course_small` | 3950 × 3950 × 4700 | 7,917,855,000 | 10.8 % | 1 | 8 | PASS |
| `l_corridor_course` | 5755 × 2430 × 4700 | 6,915,150,000 | 10.5 % | 1 | 8 | PASS |
| `l_corridor_course_ver2` | 5755 × 2430 × 4700 | 6,915,150,000 | 10.5 % | 1 | 8 | PASS |

체적은 전부 해석식(바닥 L 슬래브 + 외벽 L + 내벽 L)과 mm³ 단위까지 일치.

---

## 4. 재현 / 수정 절차

전제: Windows 11 + Autodesk Inventor 2027 설치, COM ProgID `Inventor.Application` 등록.

```bash
# 1) 검증 (스키마 + 기하 일관성) — 하드 게이트
python scripts/validate_measurements.py input/<part>/measurement-input.json \
    --report output/<part>/validation-report.json

# 2) 결정론적 피처 계획
python scripts/plan_cad.py --measurements input/<part>/measurement-input.json \
    --intent input/<part>/feature-intent.json --out-dir output/<part>

# 3) Inventor COM 빌드 → .ipt → 검증 → 리포트  (반드시 Windows PowerShell 5.1)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/inventor_build.ps1 \
    -PlanPath output/<part>/cad-plan.json
```

`<part>` = `l_course_big` 또는 `l_course_small` 또는 `l_corridor_course_ver2`.
(`l_corridor_course` 의 입력은 `input/wall_panel_corner_module/measurement-input.json` 에 있음 — §6 참조.)

**치수만 바꿔 재빌드:** 해당 `input/<part>/measurement-input.json` 의 `value` 만 수정 →
위 3단계 재실행. 파일명은 그대로 갱신된다.

**제약(검증기가 강제):**
`lane_width + 2 × wall_thickness < seg_a_length` **그리고** `< seg_b_length`,
그리고 `floor_thickness < wall_height`.

---

## 5. 좌표계 · 파라미터 (모든 파트 공통)

- **원점 O** = L자의 바깥(볼록) 코너, 바닥면.
- **+X** = leg B 방향 · **+Y** = leg A 방향 · **+Z** = 위.
- 바닥 슬래브: L 전체 풋프린트, Z 0..`floor_thickness`.
- 외벽: `X=0`(leg A) 및 `Y=0`(leg B) 모서리, Z 0..`wall_height`, 두께 `wall_thickness`.
- 내벽: 안쪽으로 `lane_width + wall_thickness` 오프셋, 동일 두께·높이. **= 사진의 검은 패널 벽**(오목 모서리).
- 통로(lane): 내·외벽 사이 순폭 `lane_width`, **leg A·leg B 양 끝 개방**.

| 측정 ID | 이름 | 의미 |
|---|---|---|
| M001 | `seg_a_length` | O에서 leg A 개방단까지 외곽 길이 |
| M002 | `seg_b_length` | O에서 leg B 개방단까지 외곽 길이 |
| M003 | `lane_width` | 통로 순폭 |
| M004 | `wall_thickness` | 내·외벽 공통 두께 |
| M005 | `wall_height` | 바닥(Z=0)에서 벽 상단까지 |
| M006 | `floor_thickness` | 바닥 슬래브 두께 |
| D001 | `strip_width` | `= M003 + 2·M004` (다리 전체폭) |
| D002 | `inner_off` | `= M003 + M004` (내벽 오프셋) |

> **중요한 데이텀 변환:** 사용자가 부르는 다리 길이(예: 5220, 5000, 1520)는
> **내측(검은 벽) 꼭짓점 기준**이다. 모델의 `seg_*_length` = (내측 기준 길이) + (안목 폭).
> 예: 큰 L `seg_a_length` = 5220 + 5450 = **10670**. 이 변환을 놓쳐 초기에 여러 번 재빌드했음.

---

## 6. 주의사항 / 함정

1. **PowerShell 버전:** Inventor COM 단계는 **Windows PowerShell 5.1 (`powershell.exe`, STA)** 에서만.
   `pwsh` 7 은 MTA라 일부 COM 호출이 조용히 null 반환. 러너 스크립트가 STA 아니면 실행 거부한다.
2. **`input/wall_panel_corner_module/` 폴더:** 이름은 옛 가설("벽 패널 코너 모듈")에서 유래.
   현재 내용은 **L자 코리도 재사용 템플릿**(`feature-intent.json` = 8-피처, `measurement-request.json` = 빈 템플릿).
   `measurement-input.json` 에는 `l_corridor_course` v1 실제값(2430/5755/1000/100/4700/50)이 들어 있다. 헷갈리지 말 것.
3. **러너 능력 한계(왜 이렇게 만들었나):**
   - `rectangle` 프로파일은 `corner: origin` / `center` 만. 임의 평면내 위치 배치 불가 → 모든 사각형이 원점에서 성장.
   - `polyline`/슬롯형 프로파일 미구현. 오프셋 스케치 평면은 평면 법선 방향으로만.
   - `rectangular_pattern` 은 전역 X(또는 X+Y)만. Y단독·Z 불가.
   - fillet/chamfer 셀렉터는 `all_vertical_outer` 만 구현.
   → L자를 "솔리드 L 프리즘 → 관통 절삭 → 바닥·외벽 add" 8-피처로 구성한 이유.
4. **검증은 바디 수만 보지 않는다:** `.ipt` 재오픈 후 RangeBox == (seg_b × seg_a × wall_height),
   MassProperties.Volume == 해석식 값(§ 엔지니어링 문서), 채움률 상식 확인까지 수행. 형상 붕괴(박스화)를 이걸로 잡아냈다.
5. **미모델링 항목:** 엔드 캡, 램프, 필렛/모따기, 패널 분할선·초록 띠·걸레받이 등 마감 디테일, 표면 텍스처.
   벽 두께·바닥 두께는 실측 불가로 공칭/시뮬값.
6. **`.git` 없음:** 이 저장소는 git 관리가 아니다. 산출물은 파일로만 존재. `output/*/OldVersions/` 는 Inventor 자동 백업.

---

## 7. 다음 작업 후보

- `l_course_combined` (본 문서 범위 밖): 큰 L + 작은 L 을 layout B로 합친 버전. 이미 빌드됨(`output/l_course_combined/`).
- 합친 버전의 "바닥+벽(속 빈)" 형태 — 계단형 내측 경계라 피처 증가하나 가능.
- 실측 재확인 시 `input/<part>/measurement-input.json` 갱신 후 재빌드.
- Isaac Sim 임포트 파이프라인(`.ipt` → USD/OBJ) 은 본 저장소 범위 밖.

---

## 8. 참고 파일

| 목적 | 경로 |
|---|---|
| 사진 원본 | `corner_line/90_degree_corner_1.jpg`, `..._2.jpg` |
| 주석 사진 (측정 위치) | `corner_line/annotated_corner_1.png`, `annotated_corner_2.png` |
| 평면도 재구성 | `corner_line/plan_v4.png` (최종), `plan_v3.png`, `plan_view.png` |
| 파이프라인 스펙 | `docs/spec/00..07` + `docs/spec/TRACEABILITY.md` |
| 스키마 | `schemas/measurement.schema.json`, `schemas/cad-feature-plan.schema.json` |
| 엔지니어링 상세 | `docs/l-courses/02-ENGINEERING.md` |
| 파트 명세 | `docs/l-courses/03-SPECIFICATION.md` |
