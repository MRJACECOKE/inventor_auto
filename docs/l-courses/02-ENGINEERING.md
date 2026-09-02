# 엔지니어링 문서 — L자 코스 생성 파이프라인 및 구성 기법

> 범위: `corner_line` 사진 기반 L자 코스 (`l_course_big`, `l_course_small`,
> `l_corridor_course`, `l_corridor_course_ver2`). `l_course_combined` 제외.

---

## 1. 목적과 맥락

`corner_line/90_degree_corner_1.jpg`, `90_degree_corner_2.jpg` 는 어떤 부품 사진이 아니라
**Isaac Sim 시뮬레이션의 코스 레퍼런스**(90° 코너가 있는 실내 복도)이다. 목표는 사진 속
공간을 로봇이 주행할 수 있는 **L자 복도 형상**으로 파라메트릭 `.ipt` 화하는 것.

설계 기조:
- 사진 = **구조만** (위상, 코너, 대칭, 개방단). 치수는 사진에서 읽지 않는다.
- 사용자의 `measurement-input.json` = 모든 실제 길이의 **단일 진실원천(SSOT)**.
- Inventor 실행 전에 **스키마 + 기하 일관성** 검증 통과 필수.
- 요구 → JSON 필드 → 파라미터 → 피처 **추적성** 유지.
- 디스크에 **검증된 `.ipt`** 없이는 성공이라고 하지 않는다.

---

## 2. 파이프라인 (Phase A–I)

```
A 이미지 인테이크        사진 경로/붙여넣기 수령. Inventor 미기동.
B 시각 구조 분석         IMAGE ANALYSIS 블록: 코너/면/대칭/개방단. mm·deg 없음.
C 측정 요청 생성         measurement-request.json (전 value=null) + feature-intent.json
D 사용자 실측 입력       measurement-input.json (value 채움)
E 검증 (하드 게이트)     scripts/validate_measurements.py  → 스키마 → 기하 일관성
F 피처 계획              scripts/plan_cad.py  → cad-plan.json/.md (결정론적, 토폴로지 정렬, sha256)
G Inventor 빌드          scripts/inventor_build.ps1  (STA) → 사용자 파라미터 → 스케치 → 피처 → Update → SaveAs
H 검증                   scripts/verify_ipt.ps1  재오픈, 바디/피처/건강도
I 리포트                 build-report.md (파라미터 맵 포함) + build-log.txt
```

E 실패 시 `MEASUREMENT_VALIDATION_FAILED` + 위반 ID 출력, Inventor 미실행.

---

## 2.1 파이프라인 플로우 다이어그램

아래 플로우는 사진 1장(들)에서 검증된 `.ipt` 까지의 전 과정을 단계 전이로 보여준다.

[[FLOW_DIAGRAM]]

### 단계 전이 설명

| 전이 | 내용 | 산출/도구 |
|---|---|---|
| **A → B** | 사진 수령 즉시 Inventor는 절대 기동하지 않는다. 이미지는 위상·코너·대칭·개방단 등 **구조만** 추출 대상이다. | IMAGE ANALYSIS 블록 (mm/deg 금지) |
| **B → C** | 분석으로부터 빌드에 필요한 치수 항목을 열거하고, 각 항목이 어떤 파라미터를 구동하는지(feature-intent)와 함께 요청서를 생성한다. | `measurement-request.json` (전 `value: null`) + `feature-intent.json` |
| **C → D** | 사용자가 현장에서 잰 실제 길이로 `null` 을 채운다. 이 파일이 이후 모든 치수의 **단일 진실원천(SSOT)** 이다. | `measurement-input.json` |
| **D → E** | 스키마 검증(형식·타입·단위·필수값) 후 기하 일관성 검증(양수성, 파생식, 유효 L 조건 `strip_width < seg_a/seg_b`, `floor_thickness < wall_height` 등). | `validate_measurements.py --report` |
| **E → D** (빨강 점선) | 어느 한 검사라도 실패하면 `MEASUREMENT_VALIDATION_FAILED` 와 위반 ID를 출력하고 **여기서 멈춘다. Inventor는 실행되지 않는다.** 사용자가 실측을 고쳐 D로 복귀한다. | 게이트 |
| **E → F** | 클린 통과 시에만 진행. 측정 JSON + feature-intent 로부터 파라미터를 측정 ID에 바인딩하고, `depends_on` 위상정렬로 피처 순서를 확정하며, 입력 sha256 을 provenance 로 기록한다. 미바인딩 치수·지연 피처는 거부. | `plan_cad.py` → `cad-plan.json` / `.md` (결정론적) |
| **F → G** | 계획을 Inventor COM으로 실행: 사용자 파라미터 생성 → 스케치(전부 XY, 원점정렬 사각형) → 피처(8개) → `Document.Update()` → `SaveAs <part>.ipt`. **반드시 Windows PowerShell 5.1 (STA)** — `pwsh` 7 은 MTA라 COM null 반환. | `inventor_build.ps1` |
| **G → H** | 저장된 `.ipt` 를 새로 재오픈해 검사: 파일 존재·`.ipt`·size>0·`kPartDocumentObject`·솔리드 바디 ≥ 1·건강하지 않은 피처 0. 이어서 형상 확인(RangeBox == seg_b × seg_a × wall_height, MassProperties.Volume == 해석식). | `verify_ipt.ps1` + §7 |
| **H → F** (주황 점선) | 빌드는 됐으나 형상이 붕괴(예: 파라미터 오입력으로 박스화)했거나 건강하지 않은 피처가 있으면 성공으로 인정하지 않고 피처 계획으로 되돌아간다. | — |
| **H → I** | `Result: PASS` 일 때만 최종 리포트를 쓴다: 입력·provenance, 검증 결과, 파라미터 맵 `M-ID → p_name → dim → feature`, 피처 목록, Inventor 결과, 경고, PASS/FAIL. | `build-report.md` + `build-log.txt` |

핵심 성질 두 가지:
1. **E는 하드 게이트다.** 검증이 클린하지 않으면 Inventor는 한 번도 실행되지 않는다.
2. **성공 판정은 디스크의 검증된 `.ipt` 로만 한다.** 바디 수만 보지 않고 bbox·체적까지 해석식과 대조한다(§7).

---

## 3. 실행 환경

| 관심사 | 런타임 | 이유 |
|---|---|---|
| 스키마·기하 검증, 피처 계획 | Python 3.9+ (stdlib. `jsonschema` 있으면 사용, 없으면 `scripts/_schema_lite.py`) | pip 불필요 |
| Inventor COM 자동화, `.ipt` 검증 | **Windows PowerShell 5.1 (`powershell.exe`, STA)** | 무설치로 `Inventor.Application` 접근 가능한 유일 경로. `pwsh` 7 은 MTA → 일부 COM 호출 null |
| 비-Inventor 테스트 | Python `unittest` | 의존성 없음 |

Inventor: 2027.1 (Build 311270010, 270A) 확인. `inventor_build.ps1` 은 major < 31 이면 BLOCKED.

---

## 4. 러너 능력 봉투 (구성 기법의 전제)

PowerShell v1 러너(`scripts/lib/*.ps1`)가 실제로 만들 수 있는 것:

| 가능 | 제약 |
|---|---|
| `rectangle` / `circle` / `polygon` 프로파일 | `rectangle` 은 `corner: origin`(좌하단=스케치 원점) 또는 `center` 만. **임의 평면내 위치 배치 불가** |
| 오프셋 스케치 평면 | 원점 평면의 **법선 방향**으로만 (XY→±Z 등) |
| `base_extrude` / `extrude_add` / `extrude_cut` (거리 또는 through-all) | — |
| `hole` (임의 x/y 배치), `slot` | 단일 점 / 축정렬. 큰 사각형엔 못 씀 |
| `rectangular_pattern` | 전역 **X**(또는 X+Y 동시)만. Y단독·Z 불가 |
| `fillet` / `chamfer` | 셀렉터 `all_vertical_outer` **만** 구현 |
| `polyline` 프로파일 | 스키마엔 있으나 **미구현** |

결론: 자유 배치가 불가하므로 **모든 사각형은 원점(0,0)에서 성장**해야 하고, 오프셋된
형상(내벽 등)은 "솔리드를 세운 뒤 원점정렬 블록으로 관통 절삭"으로 만든다.

---

## 5. L자 복도 구성 기법 (8 피처, 전부 원점정렬)

### 5.1 좌표계

- 원점 **O** = L자 바깥(볼록) 코너, 바닥면.
- **+X** = leg B · **+Y** = leg A · **+Z** = 위.
- 스케치 평면: 전부 **XY**, 프로파일 `rectangle`, `corner: origin`.

### 5.2 파라미터

| 파라미터 | 정의 |
|---|---|
| `seg_a_length` (M001) | O→leg A 개방단 외곽 길이 |
| `seg_b_length` (M002) | O→leg B 개방단 외곽 길이 |
| `lane_width` (M003) | 통로 순폭 |
| `wall_thickness` (M004) | 내·외벽 공통 두께 |
| `wall_height` (M005) | Z=0 → 벽 상단 |
| `floor_thickness` (M006) | 바닥 슬래브 두께 |
| `strip_width` (D001) | `lane_width + 2·wall_thickness` — 다리 전체폭(양 벽 포함) |
| `inner_off` (D002) | `lane_width + wall_thickness` — O에서 내벽 안쪽면까지 |

### 5.3 피처 순서

| # | 피처 | 스케치 (폭 × 높이, 원점) | 압출 | 효과 |
|---|---|---|---|---|
| F001 | base_extrude | S1 `strip_width` × `seg_a_length` | +Z `wall_height` (신규 바디) | leg A 솔리드 프리즘 |
| F002 | extrude_add | S2 `seg_b_length` × `strip_width` | +Z `wall_height` (조인) | leg B 프리즘 → 꽉 찬 L 프리즘 완성 |
| F003 | extrude_cut | S3 `inner_off` × `seg_a_length` | through-all | leg A 안쪽을 내벽 위치까지 절삭 |
| F004 | extrude_cut | S4 `seg_b_length` × `inner_off` | through-all | leg B 안쪽 절삭 → **내벽 L**만 잔존 (두께 = `strip_width − inner_off` = `wall_thickness`) |
| F005 | extrude_add | S5 `strip_width` × `seg_a_length` | +Z `floor_thickness` | 바닥 슬래브 leg A |
| F006 | extrude_add | S6 `seg_b_length` × `strip_width` | +Z `floor_thickness` | 바닥 슬래브 leg B → L 슬래브 완성 |
| F007 | extrude_add | S7 `wall_thickness` × `seg_a_length` | +Z `wall_height` | 외벽 leg A (X=0) |
| F008 | extrude_add | S8 `seg_b_length` × `wall_thickness` | +Z `wall_height` | 외벽 leg B (Y=0) |

결과: **1 솔리드 바디** = L자 바닥 슬래브 + 외벽(X=0 / Y=0) + 내벽(오프셋 `inner_off`),
그 사이 순폭 `lane_width` 통로, leg A·leg B 양 끝 개방.

F005·F006(바닥)을 F007·F008(외벽)보다 먼저 추가하는 이유: 나중에 추가되는 모든 솔리드가
기존 바디와 겹쳐 붙도록(분리된 덩어리 방지).

### 5.4 유효 조건

- `strip_width < seg_a_length` **그리고** `strip_width < seg_b_length` (아니면 노치가 사라져 박스화)
- `floor_thickness < wall_height`
- 이름 휴리스틱상 길이류(width/height/length/thickness/…)는 전부 > 0

---

## 6. 데이텀 변환 (사용자 실측 → 모델 파라미터)

사용자가 부르는 다리 길이는 **내측(검은 벽) 꼭짓점 기준**의 순길이다. 모델의
`seg_*_length` 는 **O(바깥 코너) 기준 외곽 길이**이므로 안목 폭을 더한다.

```
seg_a_length = (내측 기준 leg A 길이) + lane_width
seg_b_length = (내측 기준 leg B 길이) + lane_width
```

| 파트 | 내측 기준 leg1 / leg2 | 안목 폭 | → seg_a_length / seg_b_length |
|---|---|---|---|
| `l_course_big` | 5220 / 5000 | 5450 | 10670 / 10450 |
| `l_course_small` | 1520 / 1520 | 2430 | 3950 / 3950 |

(`l_corridor_course` / `_ver2` 는 파이프라인 검증용이라 임의값 2430 / 5755, lane 1000 을
직접 `seg_*_length` 로 사용 — 데이텀 변환 없음.)

---

## 7. 검증 방법 (Phase H + 형상 확인)

### 7.1 `verify_ipt.ps1` (자동)

파일 존재 · 확장자 `.ipt` · size > 0 · 재오픈 시 `kPartDocumentObject` ·
솔리드 바디 ≥ 1 · 피처 수 · 건강하지 않은 피처 0. `Result: PASS` 아니면 성공 아님.

### 7.2 형상 확인 (추가 수행)

바디 수만으로는 형상 붕괴(예: 파라미터 오입력으로 L이 박스화)를 못 잡는다. 그래서 `.ipt`
재오픈 후:

- **RangeBox** == (`seg_b_length` × `seg_a_length` × `wall_height`), MinPoint == (0,0,0)
- **MassProperties.Volume** == 해석식 값 (아래)
- **채움률** = Volume / (bbox 체적) — 속 빈 L 복도면 한 자릿수~10%대

### 7.3 해석 체적식 (mm)

```
strip = lane_width + 2·wall_thickness
io    = lane_width + wall_thickness            (inner_off)

A_floor_L(w) = w·seg_a_length + seg_b_length·w − w²          # 두께 w 인 L 풋프린트 면적
V_floor      = A_floor_L(strip) · floor_thickness            # 바닥 슬래브
V_outer      = A_floor_L(wall_thickness) · wall_height       # 외벽 L
A_inner_L    = wall_thickness·(seg_a_length − io)
             + (seg_b_length − io)·wall_thickness
             − wall_thickness²
V_inner      = A_inner_L · wall_height                       # 내벽 L
V_overlap    = (A_floor_L(wall_thickness) + A_inner_L) · floor_thickness   # 바닥과 벽의 Z 0..floor_t 중복

V_total = V_floor + V_outer + V_inner − V_overlap
```

검증 결과 (전부 mm³, 실측 == 해석):

| 파트 | V_total (해석 = 실측) | bbox 체적 | 채움률 |
|---|---|---|---|
| `l_course_big` | 25,860,025,000 | 524,053,705,000 | 4.9 % |
| `l_course_small` | 7,917,855,000 | 73,336,175,000 | 10.8 % |
| `l_corridor_course` | 6,915,150,000 | 65,727,855,000 | 10.5 % |

---

## 8. 결정론성 보장 (계획 단계)

- JSON: 키 정렬, `\n` 개행, 2칸 들여쓰기.
- 피처 순서 = `depends_on` 위상정렬, 동률은 피처 ID.
- `cad-plan.json` 내부에 타임스탬프 없음 (타임스탬프는 리포트/로그에만).
- 파라미터명 = 측정 `name` 에서 결정론적 (`p_<snake_case>`, 충돌 시 ID 순 숫자 접미).
- `plan_cad.py` 는 `schemas/cad-feature-plan.schema.json` 로 자기검증, 미바인딩 치수 및
  지연 피처(`shell`, `thread`, `work_plane`, `work_axis`) 거부.

---

## 9. 미모델링 / 한계

| 항목 | 처리 |
|---|---|
| 벽 두께 | 격실(파티션)이라 정밀 측정 불가 → 공칭 100 mm(초기본) / 150 mm(큰·작은 L) |
| 바닥 슬래브 두께 | 측정 불가 → 시뮬값 50 mm |
| 엔드 캡 / 개방단 마감 | 미모델링 (양 끝 개방) |
| 램프, 필렛, 모따기 | 미모델링 |
| 패널 분할선, 초록 띠, 걸레받이, 밝은 코너 스트립 | 표면 마감 → 미모델링 (별도 치수 도면 필요) |
| 표면 텍스처 / 재질 | `material.name = concrete` 메타만, 물성 미설정 |

---

## 10. 관련 문서 · 코드

| | |
|---|---|
| 인수인계 | `docs/l-courses/01-HANDOFF.md` |
| 파트 명세 | `docs/l-courses/03-SPECIFICATION.md` |
| 파이프라인 스펙 | `docs/spec/00..07`, `docs/spec/TRACEABILITY.md` |
| 검증 스크립트 | `scripts/validate_measurements.py` |
| 계획 스크립트 | `scripts/plan_cad.py` |
| 빌드 오케스트레이터 | `scripts/inventor_build.ps1` + `scripts/lib/{units,geometry,features,json}.ps1` |
| `.ipt` 검증 | `scripts/verify_ipt.ps1` |
| 피처 인텐트 (재사용 템플릿) | `input/wall_panel_corner_module/feature-intent.json` |
