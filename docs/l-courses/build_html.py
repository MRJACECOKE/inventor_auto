#!/usr/bin/env python3
"""Render the L-course .md docs to standalone, theme-aware .html (no deps).

Handles: ATX headings, GFM pipe tables, fenced code blocks, blockquotes,
ordered/unordered lists (one level), --- rules, **bold**, `code`, [text](url),
and paragraphs. Good enough for these hand-written docs; not a general parser.
"""
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
DOCS = [
    ("01-HANDOFF.md", "인수인계 문서 — L자 코스"),
    ("02-ENGINEERING.md", "엔지니어링 문서 — L자 코스 파이프라인"),
    ("02-ENGINEERING_ver2.md", "엔지니어링 문서 (쉬운 설명본) — L자 코스"),
    ("03-SPECIFICATION.md", "명세서 — L자 코스 파트"),
]

CSS = """
/* Light theme only - dark mode intentionally disabled. Font: Malgun Gothic. */
:root{
  --bg:#ffffff; --fg:#1c2024; --muted:#5b6570; --border:#d7dde3;
  --accent:#0f6fd6; --code-bg:#f4f6f8; --th-bg:#eef2f6; --quote-bg:#f6f8fa;
  color-scheme:light;
}
*{box-sizing:border-box}
html,body{background:#ffffff;}
body{background:var(--bg);color:var(--fg);margin:0;
  font:16px/1.65 "Malgun Gothic","맑은 고딕",Dotum,"돋움",sans-serif;}
.wrap{max-width:960px;margin:0 auto;padding:48px 24px 96px;}
h1,h2,h3,h4{line-height:1.3;font-weight:700;margin:1.8em 0 .6em;}
h1{font-size:1.9rem;margin-top:0;border-bottom:2px solid var(--border);padding-bottom:.3em;}
h2{font-size:1.4rem;border-bottom:1px solid var(--border);padding-bottom:.25em;}
h3{font-size:1.15rem;} h4{font-size:1rem;color:var(--muted);}
p{margin:.7em 0;} a{color:var(--accent);}
hr{border:0;border-top:1px solid var(--border);margin:2em 0;}
code{background:var(--code-bg);padding:.12em .38em;border-radius:4px;
  font:0.88em/1.5 "Malgun Gothic",Consolas,"Courier New",monospace;}
pre{background:var(--code-bg);border:1px solid var(--border);border-radius:8px;
  padding:14px 16px;overflow-x:auto;}
pre code{background:none;padding:0;font-size:0.84rem;
  font-family:Consolas,"D2Coding","Malgun Gothic","Courier New",monospace;}
blockquote{margin:1em 0;padding:.6em 1em;background:var(--quote-bg);
  border-left:3px solid var(--accent);color:var(--muted);border-radius:0 6px 6px 0;}
blockquote p{margin:.3em 0;}
ul,ol{padding-left:1.5em;} li{margin:.3em 0;}
.tablewrap{overflow-x:auto;margin:1em 0;}
table{border-collapse:collapse;width:100%;font-size:.92rem;}
th,td{border:1px solid var(--border);padding:7px 11px;text-align:left;vertical-align:top;}
th{background:var(--th-bg);font-weight:600;}
tr:nth-child(even) td{background:#f7f9fb;}
.docnav{font-size:.9rem;margin-bottom:2.5em;padding-bottom:1em;border-bottom:1px solid var(--border);}
.docnav a{margin-right:1.2em;}
figure.flow{margin:1.4em 0;padding:0;}
figure.flow svg{width:100%;height:auto;max-width:760px;display:block;
  border:1px solid var(--border);border-radius:8px;background:#fff;}
figure.flow figcaption{font-size:.85rem;color:var(--muted);margin-top:.5em;}
@media print{.docnav{display:none}body{font-size:11pt}.wrap{max-width:none}
  figure.flow svg{border:1px solid #999}}
"""

NAV = ('<div class="docnav">'
       '<a href="index.html">← 목차</a>'
       '<a href="01-HANDOFF.html">인수인계</a>'
       '<a href="02-ENGINEERING.html">엔지니어링</a>'
       '<a href="02-ENGINEERING_ver2.html">엔지니어링(쉬움)</a>'
       '<a href="03-SPECIFICATION.html">명세서</a>'
       '</div>')

# --- Pipeline flow diagram (Phase A..I). Inline SVG, light-only, self-contained. ---
_PH = [
    ("A", "이미지 인테이크", "사진 경로 수령 · Inventor 미기동"),
    ("B", "시각 구조 분석", "IMAGE ANALYSIS 블록 · mm/deg 없음"),
    ("C", "측정 요청 생성", "measurement-request.json + feature-intent.json"),
    ("D", "사용자 실측 입력", "measurement-input.json  (단일 진실원천)"),
    ("E", "검증 게이트", "validate_measurements.py · 스키마 + 기하 일관성"),
    ("F", "피처 계획", "plan_cad.py → cad-plan.json (결정론적, sha256)"),
    ("G", "Inventor 빌드", "inventor_build.ps1 · PowerShell 5.1 STA · COM"),
    ("H", "검증", "verify_ipt.ps1 + 형상 확인 (bbox · 체적)"),
    ("I", "리포트", "build-report.md + build-log.txt"),
]


def _flow_svg():
    x0, W, H, gap = 44, 452, 58, 30
    top = 26
    n = len(_PH)
    total_h = top + n * (H + gap) - gap + 24
    p = [f'<svg viewBox="0 0 760 {total_h}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="Malgun Gothic, sans-serif" role="img" '
         f'aria-label="Photo-to-IPT 파이프라인 플로우 (Phase A-I)">']
    p.append('<defs>'
             '<marker id="ah" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
             '<path d="M0,0 L7,3 L0,6 Z" fill="#334"/></marker>'
             '<marker id="ahr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
             '<path d="M0,0 L7,3 L0,6 Z" fill="#c23"/></marker>'
             '<marker id="aho" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
             '<path d="M0,0 L7,3 L0,6 Z" fill="#e58a00"/></marker>'
             '</defs>')
    cx = x0 + W / 2
    ys = [top + i * (H + gap) for i in range(n)]
    # forward connectors
    for i in range(n - 1):
        y1 = ys[i] + H
        y2 = ys[i + 1]
        p.append(f'<line x1="{cx}" y1="{y1}" x2="{cx}" y2="{y2-2}" '
                 f'stroke="#334" stroke-width="1.6" marker-end="url(#ah)"/>')
    # boxes
    for (letter, title, sub), y in zip(_PH, ys):
        fill = "#eef4fb"
        stroke = "#9db9d6"
        if letter == "E":
            fill, stroke = "#fdeef0", "#e2a9b2"
        elif letter == "G":
            fill, stroke = "#eef7ef", "#a9cdb0"
        p.append(f'<rect x="{x0}" y="{y}" width="{W}" height="{H}" rx="9" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
        p.append(f'<circle cx="{x0+27}" cy="{y+H/2}" r="15" fill="#1c2024"/>')
        p.append(f'<text x="{x0+27}" y="{y+H/2+5}" text-anchor="middle" '
                 f'fill="#fff" font-size="15" font-weight="700">{letter}</text>')
        p.append(f'<text x="{x0+52}" y="{y+23}" font-size="14.5" font-weight="700" '
                 f'fill="#1c2024">{html.escape(title)}</text>')
        p.append(f'<text x="{x0+52}" y="{y+42}" font-size="11" fill="#55606b">'
                 f'{html.escape(sub)}</text>')
    # return loop E -> D  (validation failed)
    ex = x0 + W
    yE = ys[4] + H / 2
    yD = ys[3] + H / 2
    lx = ex + 66
    p.append(f'<path d="M{ex},{yE} H{lx} V{yD} H{ex+2}" fill="none" stroke="#c23" '
             f'stroke-width="1.5" stroke-dasharray="5 4" marker-end="url(#ahr)"/>')
    p.append(f'<text x="{lx+6}" y="{(yE+yD)/2}" font-size="10.5" fill="#c23" '
             f'writing-mode="tb">VALIDATION_FAILED → 수정</text>')
    # return loop H -> F  (shape/health fail)
    yH = ys[7] + H / 2
    yF = ys[5] + H / 2
    lx2 = ex + 30
    p.append(f'<path d="M{ex},{yH} H{lx2} V{yF} H{ex+2}" fill="none" stroke="#e58a00" '
             f'stroke-width="1.5" stroke-dasharray="5 4" marker-end="url(#aho)"/>')
    p.append(f'<text x="{lx2+6}" y="{(yH+yF)/2}" font-size="10.5" fill="#e58a00" '
             f'writing-mode="tb">형상/건강도 불량 → 재계획</text>')
    p.append('</svg>')
    return "".join(p)


FLOW_BLOCK = ('<figure class="flow">' + _flow_svg() +
              '<figcaption>그림 1. Photo-to-IPT 파이프라인 (Phase A–I). 실선 = 정상 진행, '
              '빨강 점선 = 검증 실패 시 사용자 실측 수정으로 복귀(Inventor 미실행), '
              '주황 점선 = 빌드/형상 검증 실패 시 피처 계획으로 복귀.</figcaption></figure>')


def inline(t):
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def _is_table_start(lines, i):
    return ("|" in lines[i] and i + 1 < len(lines)
            and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]) is not None
            and "-" in lines[i + 1])


def render(md):
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        guard = i
        ln = lines[i]
        if ln.strip() == "[[FLOW_DIAGRAM]]":
            out.append(FLOW_BLOCK); i += 1; continue
        if ln.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(html.escape(lines[i])); i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue
        m = re.match(r"(#{1,4})\s+(.*)", ln)
        if m:
            lvl = len(m.group(1)); out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
        if re.match(r"\s*---\s*$", ln):
            out.append("<hr>"); i += 1; continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(inline(lines[i].lstrip("> ").rstrip())); i += 1
            out.append("<blockquote><p>" + "<br>".join(buf) + "</p></blockquote>")
            continue
        if _is_table_start(lines, i):
            def cells(r): return [c.strip() for c in r.strip().strip("|").split("|")]
            head = cells(ln); i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i])); i += 1
            t = ['<div class="tablewrap"><table><thead><tr>']
            t += [f"<th>{inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t)); continue
        m = re.match(r"(\s*)([-*]|\d+\.)\s+(.*)", ln)
        if m:
            ordered = bool(re.match(r"\d+\.", m.group(2)))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines):
                mm = re.match(r"(\s*)([-*]|\d+\.)\s+(.*)", lines[i])
                if not mm: break
                items.append(f"<li>{inline(mm.group(3))}</li>"); i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        if ln.strip() == "":
            i += 1; continue
        buf = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", ">", "```")) \
                and not _is_table_start(lines, i) and not re.match(r"\s*([-*]|\d+\.)\s+", lines[i]) \
                and not re.match(r"\s*---\s*$", lines[i]):
            buf.append(inline(lines[i].rstrip())); i += 1
        if buf:
            out.append("<p>" + "<br>".join(buf) + "</p>")
        if i == guard:  # safety: never spin
            i += 1
    return "\n".join(out)


def page(title, body):
    return (f"<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
            f"<body><div class=\"wrap\">{NAV}{body}</div></body></html>")


def main():
    for fn, title in DOCS:
        src = (HERE / fn).read_text(encoding="utf-8")
        (HERE / fn.replace(".md", ".html")).write_text(page(title, render(src)), encoding="utf-8")
        print("wrote", fn.replace(".md", ".html"))
    idx = """# L자 코스 문서 세트 (corner_line)

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
"""
    (HERE / "index.html").write_text(page("L자 코스 문서 세트", render(idx)), encoding="utf-8")
    (HERE / "README.md").write_text(idx, encoding="utf-8")
    print("wrote index.html, README.md")


if __name__ == "__main__":
    sys.exit(main())
