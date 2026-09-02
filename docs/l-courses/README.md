# L자 코스 문서 세트 (corner_line)

`corner_line/` 사진에서 만든 Isaac Sim용 L자 통로 CAD 문서. `l_course_combined` 제외.

- [01 · 인수인계 문서](01-HANDOFF.html) — 무엇이 어디에 있고 어떻게 재현/수정하나, 함정
- [02 · 엔지니어링 문서](02-ENGINEERING.html) — 파이프라인, 러너 한계, 8-피처 L자 구성 기법, 검증식 (정확한 원문)
- [02 · 엔지니어링 문서 (쉬운 설명본)](02-ENGINEERING_ver2.html) — 같은 내용을 전문용어 없이 다시 씀 + 용어 미니 사전
- [03 · 명세서](03-SPECIFICATION.html) — 파트별 정식 명세 (측정→파라미터 맵, 기하, 수용 기준)

## 사진 → 산출물 매핑

| 사진 | 산출물 | 핵심 |
|---|---|---|
| `90_degree_corner_1.jpg` (IMG-001) | `l_course_big` | 큰 L, 폭 5450, seg 10670/10450, 검증 PASS |
| `90_degree_corner_2.jpg` (IMG-002) | `l_course_small` | 작은 대칭 L, 폭 2430, seg 3950/3950, 검증 PASS |
| 구조 참조 (양쪽) | `l_corridor_course`, `l_corridor_course_ver2` | 파이프라인 프루프 / 스냅샷 |

## 파이프라인 플로우

[[FLOW_DIAGRAM]]

Phase A–I. E(검증)는 하드 게이트 — 클린 통과 전 Inventor 미실행. 상세는
엔지니어링 문서 §2.1.

Markdown 원본: `01-HANDOFF.md`, `02-ENGINEERING.md`, `03-SPECIFICATION.md`
(HTML 재생성: `python build_html.py`)
