#!/usr/bin/env python3
"""Build the Hebrew automation book website from a Word file using Pandoc.

This is the current preferred pipeline for the automation book:

    Word DOCX -> Pandoc semantic HTML -> RTL cleanup -> question/solution cards

It deliberately avoids page-cropping. Text stays selectable, images stay as real
images, tables stay as HTML tables, and answers are wrapped in <details> blocks
by the website renderer.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: beautifulsoup4. Install with: pip install -r requirements.txt") from exc


@dataclass(frozen=True)
class ExerciseSpec:
    number: str
    section: str
    title: str
    start: int
    end: int
    # If solution_start is set, it is used instead of looking for a פתרון marker.
    # If solution_marker=True, the split block itself is a marker and is not included.
    # If solution_marker=False, the split block is included in the hidden solution.
    solution_start: Optional[int] = None
    solution_marker: bool = True


@dataclass(frozen=True)
class ReviewPartSpec:
    label: str
    title: str
    start: int
    end: int
    solution_start: Optional[int] = None
    solution_marker: bool = True


# Explicit map for the current source file. The map is intentionally conservative:
# it keeps multi-part questions with one joint solution as one card. The review
# question 1.7.1 is rendered as one exercise with סעיפים א--ו, each with its own
# hidden solution, because pedagogically it is one exam question rather than six
# separate exercises.
EXERCISES: List[ExerciseSpec] = [
    ExerciseSpec("1.1.1", "1.1", "מערכת מכנית על שולחן חסר חיכוך", 5, 18),
    ExerciseSpec("1.1.2", "1.1", "מערכת מכנית בין תקרה לרצפה", 18, 41),
    ExerciseSpec("1.1.3", "1.1", "מודל דינמי עבור המתח על הקבל", 41, 63),
    ExerciseSpec("1.1.4", "1.1", "מודל דינמי עבור הזרם דרך הסליל", 63, 75),

    ExerciseSpec("1.2.1", "1.2", "פתרון משוואה דיפרנציאלית", 75, 100),
    ExerciseSpec("1.2.2", "1.2", "פתרון משוואה דיפרנציאלית עם שורשים מרוכבים", 100, 143),
    ExerciseSpec("1.2.3", "1.2", "פתרון משוואה דיפרנציאלית לא יציבה", 143, 186),
    ExerciseSpec("1.2.4", "1.2", "פתרון משוואה דיפרנציאלית עם שורש כפול", 186, 235),

    ExerciseSpec("1.3.1", "1.3", "התמרת לפלס, תמסורת ויציבות", 235, 277),
    ExerciseSpec("1.3.2", "1.3", "התמרת לפלס לתהליך לא יציב", 277, 319),
    ExerciseSpec("1.3.3", "1.3", "התמרת לפלס לתהליך יציב", 319, 363),
    ExerciseSpec("1.3.4", "1.3", "התמרת לפלס עם קוטב כפול", 363, 409),

    ExerciseSpec("1.4.1", "1.4", "מרחב מצבים מתוך משוואה דיפרנציאלית", 409, 428),
    ExerciseSpec("1.4.2", "1.4", "מערכת מסדר שני", 428, 454),
    ExerciseSpec("1.4.3", "1.4", "מערכת עם אינטגרל", 454, 484),
    ExerciseSpec("1.4.4", "1.4", "מערכת מסדר שלישי", 484, 513),
    ExerciseSpec("1.4.5", "1.4", "מערכת מכנית", 513, 547),
    ExerciseSpec("1.4.6", "1.4", "מערכת חשמלית", 547, 579),
    ExerciseSpec("1.4.7", "1.4", "וקטור מוצאים", 579, 601),
    ExerciseSpec("1.4.8", "1.4", "ייצוג מרחב המצבים", 601, 627),

    ExerciseSpec("1.5.1", "1.5", "מאפייני תופעות מעבר", 627, 646),
    ExerciseSpec("1.5.2", "1.5", "מערכת בתת ריסון מסדר שני", 646, 668),
    ExerciseSpec("1.5.3", "1.5", "מערכת בריסון יתר מסדר שני", 668, 689),
    ExerciseSpec("1.5.4", "1.5", "מערכת בריסון קריטי מסדר שני", 689, 712),
    ExerciseSpec("1.5.5", "1.5", "מערכת לא יציבה מסדר שני", 712, 734),
    ExerciseSpec("1.5.6", "1.5", "מערכת מסדר ראשון", 734, 748),
    ExerciseSpec("1.5.7", "1.5", "מערכת מסדר ראשון עם תנאי התחלה", 748, 770),

    ExerciseSpec("1.6.1א", "1.6", "בקר P עבור תהליך מסדר ראשון", 770, 804),
    ExerciseSpec("1.6.1ב", "1.6", "בקר P עבור תהליך מסדר שני", 804, 838),
    ExerciseSpec("1.6.2א", "1.6", "בקר PD בתת ריסון", 838, 866),
    ExerciseSpec("1.6.2ב", "1.6", "בקר PD בריסון קריטי", 866, 895),
    ExerciseSpec("1.6.3", "1.6", "בקר PI", 895, 937),

    ExerciseSpec("2.1.1", "2.1", "בקר השקייה", 1026, 1049),
    ExerciseSpec("2.1.2", "2.1", "בקר למקרר תעשייתי", 1049, 1065),
]

REVIEW_171_PARTS: List[ReviewPartSpec] = [
    ReviewPartSpec("א", "פיזיקליות ויציבות", 937, 964),
    ReviewPartSpec("ב", "ערכי מצב מתמיד", 964, 984),
    ReviewPartSpec("ג", "מרחב מצבים", 984, 990, solution_start=985, solution_marker=False),
    ReviewPartSpec("ד", "דיאגרמת חוג סגור", 991, 1004),
    ReviewPartSpec("ה", "תמסורת חוג פתוח וחוג סגור", 1004, 1011, solution_start=1006, solution_marker=False),
    ReviewPartSpec("ו", "מוצאי חוג פתוח וסגור", 1011, 1025),
]

CHAPTERS = [
    {
        "id": "chapter-1",
        "number": "1",
        "title": "מודלים ובקרה",
        "status": "implemented",
        "sections": [
            {"id": "1.1", "title": "מודלים ומערכות מכניות וחשמליות"},
            {"id": "1.2", "title": "פתרון משוואות דיפרנציאליות"},
            {"id": "1.3", "title": "התמרת לפלס ותמסורת"},
            {"id": "1.4", "title": "מרחב המצבים"},
            {"id": "1.5", "title": "תכונות של מערכות"},
            {"id": "1.6", "title": "בקרי P, PI, PD"},
            {"id": "1.7", "title": "שאלות חזרה"},
        ],
    },
    {
        "id": "chapter-2",
        "number": "2",
        "title": "לוגיקה ובקרים מתוכנתים",
        "status": "partial",
        "sections": [
            {"id": "2.1", "title": "לוגיקה", "implemented": ["2.1.1", "2.1.2"]},
            {"id": "2.2", "title": "בקרים", "comingSoon": True},
            {"id": "2.3", "title": "שאלות חזרה", "comingSoon": True},
        ],
    },
    {
        "id": "chapter-3",
        "number": "3",
        "title": "עיבוד תמונה",
        "status": "skeleton",
        "sections": [
            {"id": "3.1", "title": "ייצוג ואיחסון"},
            {"id": "3.2", "title": "סינון"},
            {"id": "3.3", "title": "סגמנטציה"},
            {"id": "3.4", "title": "מאפיינים"},
            {"id": "3.5", "title": "שאלות חזרה"},
        ],
    },
    {
        "id": "chapter-4",
        "number": "4",
        "title": "חיישנים ומפעילים",
        "status": "skeleton",
        "sections": [
            {"id": "4.1", "title": "חיישנים"},
            {"id": "4.2", "title": "מפעילים"},
            {"id": "4.3", "title": "שאלות חזרה"},
        ],
    },
]


RTL_TEXT_TAGS = {"p", "li", "td", "th", "blockquote", "figcaption"}
MATH_ANCESTORS = {"script", "style", "span", "mjx-container"}

PRIVATE_CHAR_MAP = str.maketrans({
    "\uf0ae": "→",  # Word/Symbol arrow that otherwise becomes a broken glyph.
    "\uf0a5": "∞",  # Word/Symbol infinity.
    "\u2019": "'",
})

# Text runs that should be isolated from RTL paragraphs. This does not try to
# understand mathematics; it just prevents bidi reversal of English names,
# variables, function calls, and common expressions that Pandoc leaves as text.
VAR_TOKEN = r"[A-Za-z][A-Za-z0-9_]*(?:['’])?(?:\([^א-ת\n]*?\))?"
LTR_RUN_RE = re.compile(
    r"("
    rf"(?:{VAR_TOKEN}(?:\s*[=<>+\-*/·→]\s*(?:{VAR_TOKEN}|[A-Za-z0-9_.()'’]+|∞))+ )"  # G(s)=..., t→∞, y(0)=2
    rf"|(?:{VAR_TOKEN})"  # single English/variable token
    r"|(?:\d+(?:\.\d+)?\s*(?:Kg|kg|N/m|Ns/m|N/ms|H|F|W|Ω|ohm|cm|m|s|sec))"
    r")",
    re.VERBOSE,
)

BAD_BIDI_REPLACEMENTS = [
    (re.compile(r"∞\s*→\s*t"), "t→∞"),
    (re.compile(r"∞\s*→\s*s"), "s→∞"),
    (re.compile(r"t\s*→\s*∞"), "t→∞"),
    (re.compile(r"s\s*→\s*∞"), "s→∞"),
    (re.compile(r"s\s*→\s*0"), "s→0"),
]


def run_pandoc(source: Path, temp_dir: Path) -> Path:
    media_dir = temp_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    html_path = temp_dir / "pandoc.html"
    cmd = [
        "pandoc",
        str(source),
        "-t", "html",
        "--mathjax",
        "--wrap=none",
        f"--extract-media={temp_dir}",
        "-o", str(html_path),
    ]
    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, check=True)
    except FileNotFoundError:
        raise SystemExit("Pandoc is not installed. Install pandoc, or use the generated docs folder already included in this project.")
    except subprocess.CalledProcessError as exc:
        print(exc.stdout, file=sys.stdout)
        print(exc.stderr, file=sys.stderr)
        raise SystemExit(f"Pandoc failed with exit code {exc.returncode}")
    if completed.stderr.strip():
        print(completed.stderr, file=sys.stderr)
    return html_path


def normalize_text_string(text: str) -> str:
    text = text.translate(PRIVATE_CHAR_MAP)
    text = text.replace("\u00a0", " ")
    # Add spaces around common embedded LTR expressions in Hebrew text.
    for pattern, repl in BAD_BIDI_REPLACEMENTS:
        text = pattern.sub(repl, text)
    # fix common no-space cases around English variables in Hebrew text
    text = re.sub(r"(?<=[א-ת])(?=[A-Za-z0-9])", " ", text)
    text = re.sub(r"(?<=[A-Za-z0-9)])(?=[א-ת])", " ", text)
    return text


def should_skip_text_node(node: NavigableString) -> bool:
    parent = node.parent
    while parent is not None and isinstance(parent, Tag):
        if parent.name in {"script", "style"}:
            return True
        classes = set(parent.get("class", []))
        if "math" in classes or "ltr-inline" in classes:
            return True
        parent = parent.parent
    return False


def isolate_ltr_text(soup: BeautifulSoup) -> None:
    text_nodes = list(soup.find_all(string=True))
    for node in text_nodes:
        if should_skip_text_node(node):
            continue
        original = str(node)
        normalized = normalize_text_string(original)
        if not normalized:
            if normalized != original:
                node.replace_with(normalized)
            continue
        parts = []
        last = 0
        changed = normalized != original
        for match in LTR_RUN_RE.finditer(normalized):
            token = match.group(0)
            # Do not wrap very short accidental Latin in the middle of a Hebrew word.
            if not token.strip():
                continue
            if match.start() > last:
                parts.append(NavigableString(normalized[last:match.start()]))
            span = soup.new_tag("span")
            span["class"] = "ltr-inline"
            span["dir"] = "ltr"
            span.string = token
            parts.append(span)
            last = match.end()
            changed = True
        if last < len(normalized):
            parts.append(NavigableString(normalized[last:]))
        if changed:
            node.replace_with(*parts)


HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
MATHISH_RE = re.compile(r"[A-Za-zα-ωΑ-ΩζωΣΩ]|[=<>+\-*/^²₀₁₂₃₄₅₆₇₈₉∞→∑∫√(){}\[\]]")


def is_formula_like_block(tag: Tag) -> bool:
    """True for paragraphs/cells that should be read entirely left-to-right.

    Pandoc often leaves simple equations as plain text paragraphs rather than
    MathJax. If such a paragraph is inside an RTL card, browsers may reorder
    parentheses, inequalities, and numbers visually. Marking the whole block LTR
    fixes examples such as ``1 + C(s)G(s) = 0`` and ``3 + 2Kp > 0``.
    """
    text = text_of(tag)
    if not text:
        return False
    if HEBREW_RE.search(text):
        return False
    return bool(MATHISH_RE.search(text))


def promote_formula_lines(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["p", "td", "th"]):
        if is_formula_like_block(tag):
            tag["dir"] = "ltr"
            classes = set(tag.get("class", []))
            classes.add("formula-line")
            tag["class"] = sorted(classes)


def postprocess_soup(soup: BeautifulSoup) -> None:
    # Set safe RTL defaults on semantic text blocks.
    for tag in soup.find_all(RTL_TEXT_TAGS):
        tag["dir"] = "rtl"
    # Ensure Pandoc/MathJax math is isolated from RTL text.
    for tag in soup.find_all(class_="math"):
        tag["dir"] = "ltr"
        classes = set(tag.get("class", []))
        classes.add("math")
        tag["class"] = sorted(classes)
    isolate_ltr_text(soup)
    promote_formula_lines(soup)


def normalize_media(temp_dir: Path, docs_dir: Path, soup: BeautifulSoup) -> None:
    media_src = temp_dir / "media"
    media_dst = docs_dir / "media"
    if media_dst.exists():
        shutil.rmtree(media_dst)
    media_dst.mkdir(parents=True, exist_ok=True)
    if media_src.exists():
        for src in sorted(media_src.iterdir()):
            if src.is_file():
                shutil.copy2(src, media_dst / src.name)
    for img in soup.find_all("img"):
        src = img.get("src", "")
        name = Path(src).name
        if name:
            img["src"] = f"media/{name}"
        img.attrs.pop("width", None)
        img.attrs.pop("height", None)
        style = img.get("style", "")
        style = re.sub(r"height\s*:\s*[^;]+;?", "", style)
        img["style"] = style
        img["loading"] = "lazy"
        img["dir"] = "ltr"


def text_of(tag: Tag) -> str:
    return " ".join(tag.get_text(" ", strip=True).split())


def is_solution_marker(text: str) -> bool:
    stripped = text.strip().replace("：", ":")
    return (
        stripped in {"פתרון", "פתרון:"}
        or stripped.startswith("פתרון:")
        or stripped.startswith("א. פתרון")
        or stripped.startswith("א . פתרון")
    )


def clean_fragment(tags: Iterable[Tag]) -> str:
    parts: List[str] = []
    for tag in tags:
        txt = text_of(tag)
        if not txt and not tag.find("img") and not tag.find("table"):
            continue
        cloned = BeautifulSoup(str(tag), "html.parser")
        for p in cloned.find_all("p"):
            if not p.get_text(strip=True) and not p.find("img"):
                p.decompose()
        html = str(cloned).strip()
        if html:
            parts.append(html)
    return "\n".join(parts)


def split_question_solution(children: List[Tag], spec: ExerciseSpec) -> Tuple[str, str]:
    if spec.solution_start is not None:
        split = spec.solution_start
        question_html = clean_fragment(children[spec.start:split])
        sol_start = split + 1 if spec.solution_marker else split
        solution_html = clean_fragment(children[sol_start:spec.end])
        return question_html, solution_html

    solution_idx: Optional[int] = None
    for idx in range(spec.start, spec.end):
        if is_solution_marker(text_of(children[idx])):
            solution_idx = idx
            break
    if solution_idx is None:
        return clean_fragment(children[spec.start:spec.end]), "<p>לא זוהה פתרון אוטומטית עבור שאלה זו.</p>"
    question_html = clean_fragment(children[spec.start:solution_idx])
    solution_html = clean_fragment(children[solution_idx + 1:spec.end])
    return question_html, solution_html


def exercise_id(number: str) -> str:
    return re.sub(r"[^0-9A-Za-zא-ת]+", "-", number).strip("-")


def clean_raw_pandoc_html(raw: str) -> str:
    raw = raw.translate(PRIVATE_CHAR_MAP)
    raw = raw.replace("\u00a0", " ")
    # Word sometimes exports t→∞ in the visually reversed order around an empty RTL span.
    raw = re.sub(r"(?:∞|&infin;)\s*(?:<span dir=\"rtl\"></span>)?\s*([ts])\s*→", r"\1→∞", raw)
    raw = re.sub(r"([ts])\s*→\s*(?:∞|&infin;)", r"\1→∞", raw)
    raw = re.sub(r"([ts])\s*→\s*0", r"\1→0", raw)
    return raw




def ensure_custom_assets(docs_dir: Path) -> None:
    """Copy hand-fixed assets that should override fragile Word/Pandoc output."""
    project_root = Path(__file__).resolve().parents[1]
    custom_dir = project_root / "source" / "assets"
    media_dir = docs_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    src = custom_dir / "1-7-1d-closed-loop.png"
    if src.exists():
        shutil.copy2(src, media_dir / src.name)


def review_part_solution_override(label: str, solution_html: str) -> str:
    """Override parts where Word/Pandoc breaks a visual diagram into text fragments."""
    if label == "ד":
        return (
            '<figure class="word-diagram" dir="ltr">'
            '<img src="media/1-7-1d-closed-loop.png" alt="דיאגרמת חוג סגור עם בקר PD, תתי התהליכים A ו-B, וחיישן H=1" loading="lazy" />'
            '</figure>'
        )
    return solution_html

def build_data(html_path: Path, temp_dir: Path, docs_dir: Path) -> dict:
    raw_html = clean_raw_pandoc_html(html_path.read_text(encoding="utf-8"))
    soup = BeautifulSoup(raw_html, "html.parser")
    normalize_media(temp_dir, docs_dir, soup)
    postprocess_soup(soup)
    body = soup.body or soup
    children = [c for c in body.children if isinstance(c, Tag)]
    ensure_custom_assets(docs_dir)

    max_end = max(spec.end for spec in EXERCISES)
    if len(children) < max_end:
        raise SystemExit(f"Pandoc produced only {len(children)} top-level blocks, but the map expects at least {max_end}.")

    exercises = []
    for spec in EXERCISES:
        # Insert the grouped review question immediately before Chapter 2.
        if spec.number == "2.1.1":
            parts = []
            for part in REVIEW_171_PARTS:
                part_spec = ExerciseSpec(
                    number=f"1.7.1{part.label}",
                    section="1.7",
                    title=part.title,
                    start=part.start,
                    end=part.end,
                    solution_start=part.solution_start,
                    solution_marker=part.solution_marker,
                )
                q_html, s_html = split_question_solution(children, part_spec)
                s_html = review_part_solution_override(part.label, s_html)
                parts.append({
                    "label": part.label,
                    "title": part.title,
                    "questionHtml": q_html,
                    "solutionHtml": s_html,
                })
            exercises.append({
                "id": exercise_id("1.7.1"),
                "number": "1.7.1",
                "section": "1.7",
                "title": "שאלת חזרה: מועד א׳ 2026 סמסטר א",
                "questionHtml": "<p>השאלה מחולקת לסעיפים א–ו. לכל סעיף יש פתרון נפרד שנפתח בלחיצה.</p>",
                "parts": parts,
            })

        question_html, solution_html = split_question_solution(children, spec)
        if not question_html.strip():
            raise SystemExit(f"Empty question HTML for {spec.number}")
        exercises.append({
            "id": exercise_id(spec.number),
            "number": spec.number,
            "section": spec.section,
            "title": spec.title,
            "questionHtml": question_html,
            "solutionHtml": solution_html,
        })

    return {
        "source": "source/Automation_book22June2026.docx",
        "build": "pandoc-html-rtl-v5",
        "notes": "Chapter 1 plus 2.1.1 and 2.1.2. Exercise 1.7.1 is one review question with סעיפים א–ו, each with its own hidden solution. Formula-like plain-text paragraphs are forced LTR. 1.7.1 סעיף ד uses a hand-fixed diagram image because Pandoc breaks that Word drawing into text fragments.",
        "chapters": CHAPTERS,
        "exercises": exercises,
    }


def write_book_data(data: dict, docs_dir: Path) -> None:
    assets = docs_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    js = "window.BOOK_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
    (assets / "book-data.js").write_text(js, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Path to Automation_book22June2026.docx")
    parser.add_argument("--out", type=Path, default=Path("docs"), help="Output docs directory")
    args = parser.parse_args()

    source = args.source
    docs_dir = args.out
    if not source.exists():
        raise SystemExit(f"Word source not found: {source}")
    docs_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        html_path = run_pandoc(source, temp_dir)
        data = build_data(html_path, temp_dir, docs_dir)
    write_book_data(data, docs_dir)
    print(f"Built {len(data['exercises'])} exercises from {source} into {docs_dir}")


if __name__ == "__main__":
    main()
