#!/usr/bin/env python3
"""Build the Hebrew automation book website from a Word file.

This is the current preferred pipeline for the automation book:

    Word DOCX -> semantic HTML + rendered Word drawings -> question/solution cards

Text stays selectable, normal images stay as real images, and tables stay as
HTML tables. Word drawing canvases (shapes, connectors, grouped pictures) are
rendered from small temporary DOCX files and trimmed automatically. This keeps
diagrams intact without maintaining page numbers or hand-written crop boxes.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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
    visual: Optional[str] = None


@dataclass(frozen=True)
class PartSpec:
    label: str
    title: str
    start: int
    end: int
    solution_start: Optional[int] = None
    solution_marker: bool = True
    visual: Optional[str] = None


@dataclass(frozen=True)
class GroupedExerciseSpec:
    number: str
    section: str
    title: str
    intro_start: int
    intro_end: int
    parts: Sequence[PartSpec]


@dataclass(frozen=True)
class WordVisualSpec:
    key: str
    filename: str
    paragraphs: Sequence[int]
    alt: str
    body_elements: Sequence[int] = ()


# Explicit semantic map for Automation_book16July2026_1_updated(1).docx. The Word file does
# not use heading styles consistently, so stable top-level Pandoc block boundaries
# are used for text. Multi-part exam questions remain one card with one <details>
# solution per סעיף.
EXERCISES: List[ExerciseSpec] = [
    ExerciseSpec("1.1.1", "1.1", "מערכת מכנית על שולחן חסר חיכוך", 5, 18),
    ExerciseSpec("1.1.2", "1.1", "מערכת מכנית בין תקרה לרצפה", 18, 41),
    ExerciseSpec("1.1.3", "1.1", "מודל דינמי עבור המתח על הקבל", 41, 57, visual="1-1-3-solution"),
    ExerciseSpec("1.1.4", "1.1", "מודל דינמי עבור הזרם דרך הסליל", 57, 69),

    ExerciseSpec("1.2.1", "1.2", "פתרון משוואה דיפרנציאלית", 69, 94),
    ExerciseSpec("1.2.2", "1.2", "פתרון משוואה דיפרנציאלית עם שורשים מרוכבים", 94, 137),
    ExerciseSpec("1.2.3", "1.2", "פתרון משוואה דיפרנציאלית לא יציבה", 137, 179),
    ExerciseSpec("1.2.4", "1.2", "פתרון משוואה דיפרנציאלית עם שורש כפול", 179, 228),

    ExerciseSpec("1.3.1", "1.3", "התמרת לפלס, תמסורת ויציבות", 228, 270),
    ExerciseSpec("1.3.2", "1.3", "התמרת לפלס לתהליך לא יציב", 270, 312),
    ExerciseSpec("1.3.3", "1.3", "התמרת לפלס לתהליך יציב", 312, 356),
    ExerciseSpec("1.3.4", "1.3", "התמרת לפלס עם קוטב כפול", 356, 402),

    ExerciseSpec("1.4.1", "1.4", "מרחב מצבים מתוך משוואה דיפרנציאלית", 402, 421),
    ExerciseSpec("1.4.2", "1.4", "מערכת מסדר שני", 421, 447),
    ExerciseSpec("1.4.3", "1.4", "מערכת עם אינטגרל", 447, 477),
    ExerciseSpec("1.4.4", "1.4", "מערכת מסדר שלישי", 477, 506),
    ExerciseSpec("1.4.5", "1.4", "מערכת מכנית", 506, 540),
    ExerciseSpec("1.4.6", "1.4", "מערכת חשמלית", 540, 572),
    ExerciseSpec("1.4.7", "1.4", "וקטור מוצאים", 572, 594),
    ExerciseSpec("1.4.8", "1.4", "ייצוג מרחב המצבים", 594, 620),

    ExerciseSpec("1.5.1", "1.5", "מאפייני תופעות מעבר", 620, 639),
    ExerciseSpec("1.5.2", "1.5", "מערכת בתת ריסון מסדר שני", 639, 661),
    ExerciseSpec("1.5.3", "1.5", "מערכת בריסון יתר מסדר שני", 661, 682),
    ExerciseSpec("1.5.4", "1.5", "מערכת בריסון קריטי מסדר שני", 682, 705),
    ExerciseSpec("1.5.5", "1.5", "מערכת לא יציבה מסדר שני", 705, 727),
    ExerciseSpec("1.5.6", "1.5", "מערכת מסדר ראשון", 727, 741),
    ExerciseSpec("1.5.7", "1.5", "מערכת מסדר ראשון עם תנאי התחלה", 741, 763),

    ExerciseSpec("1.6.1א", "1.6", "בקר P עבור תהליך מסדר ראשון", 764, 800, solution_start=772),
    ExerciseSpec("1.6.1ב", "1.6", "בקר P עבור תהליך מסדר שני", 800, 835, solution_start=808),
    ExerciseSpec("1.6.2א", "1.6", "בקר PD בתת ריסון", 836, 866, solution_start=846),
    ExerciseSpec("1.6.2ב", "1.6", "בקר PD בריסון קריטי", 866, 899, solution_start=876),
    ExerciseSpec("1.6.3", "1.6", "בקר PI", 900, 939, solution_start=911),

    ExerciseSpec("1.7.4", "1.7", "בקרת מהירות לרכב", 1126, 1166, solution_start=1130, visual="1-7-4"),

    ExerciseSpec("2.1.1", "2.1", "בקר השקייה", 1212, 1229, solution_start=1214, visual="2-1-1-karnaugh"),
    ExerciseSpec("2.1.2", "2.1", "בקר למקרר תעשייתי", 1229, 1245, solution_start=1232, visual="2-1-2-karnaugh"),

    ExerciseSpec("4.1.1", "4.1", "שגיאה מוחלטת ושגיאה יחסית", 1251, 1270, solution_start=1257),
    ExerciseSpec("4.1.2", "4.1", "ממוצע מדידות וחזרתיות", 1270, 1287, solution_start=1276),
    ExerciseSpec("4.1.3", "4.1", "מערכת מדידה עם המרה ליניארית", 1287, 1306, solution_start=1294),
    ExerciseSpec("4.2.1", "4.2", "תחום, טווח ו־FSD", 1307, 1328, solution_start=1315),
    ExerciseSpec("4.2.2", "4.2", "רזולוציה של חיישן", 1328, 1349, solution_start=1338),
    ExerciseSpec("4.2.3", "4.2", "לינאריות ושגיאת אי־לינאריות", 1349, 1380, solution_start=1359),
    ExerciseSpec("4.3.1", "4.3", "רזולוציית ממיר A/D", 1381, 1389, solution_start=1384),
    ExerciseSpec("4.3.2", "4.3", "קצב דגימה מינימלי", 1389, 1398, solution_start=1392),
    ExerciseSpec("4.3.3", "4.3", "כמות דגימות", 1398, 1407, solution_start=1401),
    ExerciseSpec("4.4.1", "4.4", "תיקון Offset", 1408, 1430, solution_start=1417),
    ExerciseSpec("4.4.2", "4.4", "מציאת קבוע כיול", 1430, 1449, solution_start=1439),
    ExerciseSpec("4.4.3", "4.4", "עקומת כיול ליניארית", 1449, 1477, solution_start=1459),
    ExerciseSpec("4.5.1", "4.5", "PWM ומתח ממוצע", 1478, 1487, solution_start=1482),
    ExerciseSpec("4.5.2", "4.5", "מהירות מנוע כתלות ב־PWM", 1487, 1500, solution_start=1492),
    ExerciseSpec("4.5.3", "4.5", "מומנט נדרש להרמת עומס", 1500, 1514, solution_start=1506),
    ExerciseSpec("4.6.1", "4.6", "הספק מכני של מנוע", 1515, 1525, solution_start=1518),
    ExerciseSpec("4.6.2", "4.6", "מנוע Stepper ותנועה קווית", 1525, 1534, solution_start=1529),
    ExerciseSpec("4.6.3", "4.6", "מנוע סרוו וזווית פקודה", 1534, 1552, solution_start=1541),
    ExerciseSpec("4.7.1", "4.7", "רזולוציה של אנקודר אינקרמנטלי", 1553, 1563, solution_start=1557),
    ExerciseSpec("4.7.2", "4.7", "אנקודר קוואדרטי", 1563, 1576, solution_start=1567),
    ExerciseSpec("4.7.3", "4.7", "מרחק נסיעה לפי ספירות אנקודר", 1576, 1593, solution_start=1581),
]

GROUPED_EXERCISES: List[GroupedExerciseSpec] = [
    GroupedExerciseSpec("1.7.1", "1.7", "מועד א׳ 2026 סמסטר א", 940, 943, [
        PartSpec("א", "פיזיקליות ויציבות", 943, 962, solution_start=945),
        PartSpec("ב", "ערכי מצב מתמיד", 962, 980, solution_start=966),
        PartSpec("ג", "מרחב מצבים", 980, 987, solution_start=981, solution_marker=False),
        PartSpec("ד", "דיאגרמת חוג סגור", 987, 989, solution_start=988, visual="1-7-1-d"),
        PartSpec("ה", "תמסורות חוג פתוח וסגור", 989, 997, solution_start=990, solution_marker=False),
        PartSpec("ו", "מוצאי חוג פתוח וסגור", 997, 1013, solution_start=1001),
    ]),
    GroupedExerciseSpec("1.7.2", "1.7", "מועד א׳ 2025 סמסטר ב", 1014, 1016, [
        PartSpec("א", "מודל מרחב המצבים", 1016, 1022, solution_start=1017),
        PartSpec("ב", "פיזיקליות ויציבות", 1022, 1038, solution_start=1023),
        PartSpec("ג", "ערך מצב מתמיד", 1038, 1041, solution_start=1039),
        PartSpec("ד", "דיאגרמת חוג סגור", 1041, 1044, solution_start=1042, visual="1-7-2-d"),
        PartSpec("ה", "תמסורת חוג סגור", 1044, 1051, solution_start=1045),
        PartSpec("ו", "תחומי יציבות ופיזיקליות", 1051, 1063, solution_start=1054),
    ]),
    GroupedExerciseSpec("1.7.3", "1.7", "מועד א׳ 2025 סמסטר א", 1064, 1067, [
        PartSpec("א", "פיזיקליות ויציבות", 1067, 1103, solution_start=1068),
        PartSpec("ב", "תמסורת חוג סגור", 1103, 1108, solution_start=1104, visual="1-7-3-b"),
        PartSpec("ג", "תחום קבוע הבקרה", 1108, 1119, solution_start=1110),
        PartSpec("ד", "ערכי מצב מתמיד", 1119, 1126, solution_start=1120),
    ]),
    GroupedExerciseSpec("1.7.5", "1.7", "מועד א׳ 2024 סמסטר ב", 1167, 1169, [
        PartSpec("א", "יציבות התהליך", 1169, 1176, solution_start=1171),
        PartSpec("ב", "תגובה למדרגה", 1176, 1192, solution_start=1178),
        PartSpec("ג", "דיאגרמת חוג סגור", 1192, 1194, solution_start=1193, solution_marker=False, visual="1-7-5-c"),
        PartSpec("ד", "תמסורת חוג סגור", 1194, 1197, solution_start=1195),
        PartSpec("ה", "תחום קבוע הבקרה", 1197, 1204, solution_start=1199),
        PartSpec("ו", "ריסון קריטי", 1204, 1211, solution_start=1205, solution_marker=False),
    ]),
    GroupedExerciseSpec("5.1.1", "5.1", "מועד א׳ 2026 סמסטר א", 1732, 1734, [
        PartSpec("א", "משתנה lastVal", 1734, 1737, solution_start=1735),
        PartSpec("ב", "פעולת נורת ה־LED", 1737, 1740, solution_start=1738),
        PartSpec("ג", "פיצול הטיפול בנורה", 1740, 1743, solution_start=1741),
        PartSpec("ד", "חיבור הרכיבים", 1743, 1753, solution_start=1750),
    ]),
    GroupedExerciseSpec("5.2.1", "5.2", "מועד א׳ 2025 סמסטר ב", 1754, 1758, [
        PartSpec("א", "המערכת כחיישן", 1758, 1761, solution_start=1759, visual="5-2-a"),
        PartSpec("ב", "פעולת הקוד", 1761, 1777, solution_start=1762),
        PartSpec("ג", "חיבור הרכיבים", 1777, 1780, solution_start=1778, solution_marker=False),
    ]),
    GroupedExerciseSpec("5.3.1", "5.3", "מועד א׳ 2025 סמסטר א", 1781, 1783, [
        PartSpec("א", "המערכת כחיישן", 1783, 1788, solution_start=1784),
        PartSpec("ב", "פעולת הקוד ותיקונו", 1788, 1803, solution_start=1789),
        PartSpec("ג", "חיבור הרכיבים", 1803, 1810, solution_start=1804, visual="5-3-c"),
    ]),
    GroupedExerciseSpec("5.4.1", "5.4", "מועד א׳ 2024 סמסטר ב", 1811, 1813, [
        PartSpec("א", "תיקון שגיאות בקוד", 1813, 1818, solution_start=1814),
        PartSpec("ב", "פונקציית Ginput", 1818, 1824, solution_start=1819),
        PartSpec("ג", "שינוי הגדרות הפינים", 1824, 1827, solution_start=1825),
    ]),
    GroupedExerciseSpec("5.5.1", "5.5", "מועד א׳ 2024 סמסטר א", 1828, 1830, [
        PartSpec("א", "תפקיד הארדואינו", 1830, 1833, solution_start=1831),
        PartSpec("ב", "פעולת הקוד", 1833, 1841, solution_start=1834),
        PartSpec("ג", "חיבור הרכיבים", 1841, 1845, solution_start=1842, visual="5-5-c"),
    ]),
]


WORD_VISUALS: List[WordVisualSpec] = [
    WordVisualSpec("1-1-3-solution", "word-visual-1-1-3-solution.png", [57], "מעגל חשמלי עם סימון הזרמים עבור פתרון שאלה 1.1.3"),
    WordVisualSpec("1-7-1-d", "word-visual-1-7-1-d.png", list(range(1118, 1123)), "דיאגרמת החוג הסגור עבור מועד א׳ 2026, סעיף ד"),
    WordVisualSpec("1-7-2-d", "word-visual-1-7-2-d.png", list(range(1203, 1207)), "דיאגרמת החוג הסגור עבור מועד א׳ 2025 סמסטר ב, סעיף ד"),
    WordVisualSpec("1-7-3-b", "word-visual-1-7-3-b.png", list(range(1296, 1300)), "דיאגרמת החוג הסגור עבור מועד א׳ 2025 סמסטר א, סעיף ב"),
    WordVisualSpec("1-7-4", "word-visual-1-7-4.png", list(range(1372, 1376)), "דיאגרמת חוג סגור של מערכת בקרת מהירות לרכב"),
    WordVisualSpec("1-7-5-c", "word-visual-1-7-5-c.png", list(range(1456, 1462)), "דיאגרמת החוג הסגור עבור מועד א׳ 2024 סמסטר ב, סעיף ג"),
    WordVisualSpec("2-1-1-karnaugh", "word-visual-2-1-1-karnaugh.png", [], "מפת קרנו צבעונית עבור בקר ההשקיה", body_elements=[1524]),
    WordVisualSpec("2-1-2-karnaugh", "word-visual-2-1-2-karnaugh.png", [], "מפת קרנו צבעונית עבור בקר המקרר התעשייתי", body_elements=[1557]),
    WordVisualSpec("5-2-a", "word-visual-5-2-a.png", [2249, 2250], "שרשרת האותות של המערכת האולטרסונית"),
    WordVisualSpec("5-3-c", "word-visual-5-3-c.png", list(range(2385, 2397)), "חיבור ארדואינו, מטריצת חיבורים, מיקרופון ונורות"),
    WordVisualSpec("5-5-c", "word-visual-5-5-c.png", [2525, 2526, 2527], "חיבור ארדואינו למנורת שולחן ולכפתור קפיצי"),
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
        "status": "implemented",
        "sections": [
            {"id": "4.1", "title": "מערכות מדידה"},
            {"id": "4.2", "title": "מאפייני חיישנים ומערכות מדידה"},
            {"id": "4.3", "title": "אותות ונתונים"},
            {"id": "4.4", "title": "כיול חיישנים"},
            {"id": "4.5", "title": "בקרת מנועים באמצעות PWM"},
            {"id": "4.6", "title": "מפעילים ומנועים"},
            {"id": "4.7", "title": "אנקודרים"},
        ],
    },
    {
        "id": "chapter-5",
        "number": "5",
        "title": "ארדואינו",
        "status": "implemented",
        "sections": [
            {"id": "5.1", "title": "מועד א׳ 2026 סמסטר א"},
            {"id": "5.2", "title": "מועד א׳ 2025 סמסטר ב"},
            {"id": "5.3", "title": "מועד א׳ 2025 סמסטר א"},
            {"id": "5.4", "title": "מועד א׳ 2024 סמסטר ב"},
            {"id": "5.5", "title": "מועד א׳ 2024 סמסטר א"},
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


def write_visual_docx(
    source: Path,
    output: Path,
    paragraph_indexes: Sequence[int],
    body_element_indexes: Sequence[int] = (),
) -> None:
    """Create a small DOCX containing only selected drawing-bearing paragraphs.

    All original relationships and media are kept so grouped Word shapes and
    connectors still resolve. Only document.xml is narrowed to the requested
    paragraphs. The large square page prevents anchored artwork near an original
    page edge from being clipped during conversion.
    """
    try:
        from lxml import etree
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Missing dependency: lxml. Install with: pip install -r requirements.txt") from exc

    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    qn = lambda local: f"{{{w}}}{local}"

    with zipfile.ZipFile(source, "r") as zin:
        document_xml = zin.read("word/document.xml")
        root = etree.fromstring(document_xml)
        body = root.find(qn("body"))
        if body is None:
            raise SystemExit("The Word document does not contain a document body.")
        body_elements = list(body)
        paragraphs = body.findall(qn("p"))
        original_sect_pr = body.find(qn("sectPr"))
        bad = [idx for idx in paragraph_indexes if idx < 0 or idx >= len(paragraphs)]
        if bad:
            raise SystemExit(f"Word visual paragraph indexes are out of range: {bad}; document has {len(paragraphs)} paragraphs.")
        bad_elements = [idx for idx in body_element_indexes if idx < 0 or idx >= len(body_elements)]
        if bad_elements:
            raise SystemExit(
                f"Word visual body-element indexes are out of range: {bad_elements}; "
                f"document has {len(body_elements)} body elements."
            )
        if paragraph_indexes and body_element_indexes:
            raise SystemExit("A Word visual must use paragraph indexes or body-element indexes, not both.")

        if body_element_indexes:
            selected = [copy.deepcopy(body_elements[idx]) for idx in body_element_indexes]
        else:
            selected = [copy.deepcopy(paragraphs[idx]) for idx in paragraph_indexes]
        for child in list(body):
            body.remove(child)
        for paragraph in selected:
            body.append(paragraph)

        sect_pr = copy.deepcopy(original_sect_pr) if original_sect_pr is not None else etree.Element(qn("sectPr"))
        # Preserve the original page width and horizontal margins: right-aligned
        # inline images and page-positioned connectors then retain their x offset.
        # Extra height prevents bottom-of-page drawings from being clipped.
        for ref_name in ("headerReference", "footerReference"):
            for ref in list(sect_pr.findall(qn(ref_name))):
                sect_pr.remove(ref)
        page_size = sect_pr.find(qn("pgSz"))
        if page_size is None:
            page_size = etree.SubElement(sect_pr, qn("pgSz"))
            page_size.set(qn("w"), "11906")
        page_size.set(qn("h"), "28800")
        page_margin = sect_pr.find(qn("pgMar"))
        if page_margin is None:
            page_margin = etree.SubElement(sect_pr, qn("pgMar"))
            page_margin.set(qn("top"), "720")
            page_margin.set(qn("right"), "720")
            page_margin.set(qn("left"), "720")
        page_margin.set(qn("bottom"), "360")
        page_margin.set(qn("header"), "0")
        page_margin.set(qn("footer"), "0")
        body.append(sect_pr)

        replacement = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = replacement if item.filename == "word/document.xml" else zin.read(item.filename)
                zout.writestr(item, data)


def render_pdf_to_trimmed_png(pdf_path: Path, output: Path) -> None:
    try:
        import fitz
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Missing dependency: PyMuPDF or Pillow. Install with: pip install -r requirements.txt") from exc

    rendered = []
    with fitz.open(pdf_path) as pdf:
        for page in pdf:
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), alpha=False)
            image = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
            gray = image.convert("L")
            mask = gray.point(lambda value: 255 if value < 248 else 0)
            bbox = mask.getbbox()
            if not bbox:
                continue
            padding = 36
            left = max(0, bbox[0] - padding)
            top = max(0, bbox[1] - padding)
            right = min(image.width, bbox[2] + padding)
            bottom = min(image.height, bbox[3] + padding)
            rendered.append(image.crop((left, top, right, bottom)))

    if not rendered:
        raise SystemExit(f"LibreOffice produced a blank visual: {pdf_path.name}")
    width = max(image.width for image in rendered)
    height = sum(image.height for image in rendered) + 16 * (len(rendered) - 1)
    combined = Image.new("RGB", (width, height), "white")
    y = 0
    for image in rendered:
        combined.paste(image, ((width - image.width) // 2, y))
        y += image.height + 16
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.save(output, "PNG", optimize=True)


def render_word_visuals(source: Path, docs_dir: Path, temp_dir: Path) -> Dict[str, WordVisualSpec]:
    """Render every shape-based diagram declared in WORD_VISUALS.

    Cropping is content-aware: each isolated Word drawing is converted to PDF,
    rasterized, and trimmed to its non-white bounding box.
    """
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise SystemExit("LibreOffice Writer is required to render Word drawing shapes automatically.")

    input_dir = temp_dir / "word-visual-docx"
    pdf_dir = temp_dir / "word-visual-pdf"
    profile_dir = temp_dir / "libreoffice-profile"
    input_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    docx_paths = []
    for visual in WORD_VISUALS:
        docx_path = input_dir / f"{visual.key}.docx"
        write_visual_docx(source, docx_path, visual.paragraphs, visual.body_elements)
        docx_paths.append(docx_path)

    cmd = [
        soffice,
        f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(pdf_dir),
        *[str(path) for path in docx_paths],
    ]
    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, check=True, timeout=180)
    except subprocess.CalledProcessError as exc:
        print(exc.stdout, file=sys.stdout)
        print(exc.stderr, file=sys.stderr)
        raise SystemExit(f"LibreOffice visual conversion failed with exit code {exc.returncode}")
    except subprocess.TimeoutExpired:
        raise SystemExit("LibreOffice visual conversion timed out.")
    if completed.stderr.strip():
        print(completed.stderr, file=sys.stderr)

    media_dir = docs_dir / "media"
    by_key = {visual.key: visual for visual in WORD_VISUALS}
    for visual in WORD_VISUALS:
        pdf_path = pdf_dir / f"{visual.key}.pdf"
        if not pdf_path.exists():
            raise SystemExit(f"LibreOffice did not create {pdf_path.name}.")
        render_pdf_to_trimmed_png(pdf_path, media_dir / visual.filename)
    return by_key


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


CODE_HINT_RE = re.compile(
    r"(?:#include|void\s+(?:setup|loop)|pinMode\s*\(|digitalWrite\s*\(|analogRead\s*\(|Serial\.)"
)


def promote_code_blocks(soup: BeautifulSoup) -> None:
    """Keep Arduino listings left-to-right even inside the Hebrew page."""
    for tag in soup.find_all(["ol", "blockquote", "p"]):
        text = text_of(tag)
        if len(text) < 80 or len(CODE_HINT_RE.findall(text)) < 2:
            continue
        tag["dir"] = "ltr"
        classes = set(tag.get("class", []))
        classes.add("word-code")
        tag["class"] = sorted(classes)


def merge_ltr_fragments(soup: BeautifulSoup) -> None:
    """Repair common bidi splits created by Pandoc/Word.

    Examples fixed:
    * <span class="ltr-inline">M</span><sub>1</sub>  -> one LTR unit M₁
    * <span class="ltr-inline">t</span><span dir="rtl">=3, בזמן</span>
      -> one LTR unit t=3, followed by Hebrew text.
    Keeping the full mathematical token inside one LTR isolate prevents visual
    reversal such as ``1M`` or ``t→∞ בזמן``.
    """
    def is_ltr_span(tag: Tag) -> bool:
        return isinstance(tag, Tag) and "ltr-inline" in tag.get("class", [])

    def ltr_text(tag: Tag) -> str:
        return tag.get_text("", strip=False)

    for span in list(soup.find_all(class_="ltr-inline")):
        # Move immediately following sub/sup into the same LTR isolate.
        while isinstance(span.next_sibling, Tag) and span.next_sibling.name in {"sub", "sup"}:
            span.append(span.next_sibling.extract())

        # Merge simple operator suffixes that Pandoc leaves in the following RTL
        # text node/span.  This handles t=3, y(0)=2, x_1, s→0, t→∞, etc.
        made_change = True
        while made_change:
            made_change = False
            nxt = span.next_sibling
            target = None
            if isinstance(nxt, NavigableString):
                target = nxt
                text = str(nxt)
            elif isinstance(nxt, Tag) and nxt.name == "span" and nxt.get("dir") == "rtl":
                # Only touch plain spans; do not flatten complex content.
                if len(list(nxt.children)) == 1 and isinstance(next(iter(nxt.children), None), NavigableString):
                    target = nxt
                    text = nxt.get_text("", strip=False)
                else:
                    text = ""
            else:
                text = ""
            if not target or not text:
                continue

            m = re.match(r"^(\s*(?:[_=<>≤≥+\-*/]\s*)?(?:\d+(?:\.\d+)?|[A-Za-z][A-Za-z0-9_]*(?:\([^א-ת\n]*?\))?|∞)|\s*→\s*(?:∞|0))(.*)$", text, flags=re.S)
            if not m:
                continue
            prefix, rest = m.group(1), m.group(2)
            # Avoid swallowing plain Hebrew after a number. Stop before comma/space
            # followed by Hebrew text.
            if HEBREW_RE.search(prefix):
                continue
            if not prefix.strip():
                continue
            span.append(NavigableString(prefix))
            if isinstance(target, NavigableString):
                target.replace_with(NavigableString(rest))
            else:
                target.string = rest
            made_change = True

    # If a sub/sup somehow remained immediately before an LTR span, move it in front.
    for span in list(soup.find_all(class_="ltr-inline")):
        prev = span.previous_sibling
        if isinstance(prev, Tag) and prev.name in {"sub", "sup"}:
            span.insert(0, prev.extract())


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
    merge_ltr_fragments(soup)
    promote_formula_lines(soup)
    promote_code_blocks(soup)


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


def clean_solution_fragment(tags: Iterable[Tag], strip_leading_marker: bool = False) -> str:
    html = clean_fragment(tags)
    if not strip_leading_marker or not html:
        return html
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(string=True):
        original = str(node)
        cleaned = re.sub(r"^\s*פתרון\s*:?\s*", "", original, count=1)
        if cleaned != original:
            if cleaned:
                node.replace_with(cleaned)
            else:
                node.extract()
            break
    return str(soup).strip()


def split_question_solution(children: List[Tag], spec: ExerciseSpec) -> Tuple[str, str]:
    if spec.solution_start is not None:
        split = spec.solution_start
        question_html = clean_fragment(children[spec.start:split])
        sol_start = split + 1 if spec.solution_marker else split
        solution_html = clean_solution_fragment(
            children[sol_start:spec.end],
            strip_leading_marker=not spec.solution_marker,
        )
        if not solution_html.strip():
            solution_html = '<p class="source-note">הפתרון אינו מופיע במסמך המקור.</p>'
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
    if not solution_html.strip():
        solution_html = '<p class="source-note">הפתרון אינו מופיע במסמך המקור.</p>'
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




def attach_word_visual(solution_html: str, key: Optional[str], visuals: Dict[str, WordVisualSpec]) -> str:
    if not key:
        return solution_html
    visual = visuals.get(key)
    if visual is None:
        raise SystemExit(f"Unknown Word visual key: {key}")

    soup = BeautifulSoup(solution_html, "html.parser")
    # The generated image is the complete drawing canvas. Remove Pandoc's partial
    # image fragments so the diagram is not duplicated or shown without connectors.
    for image in list(soup.find_all("img")):
        parent = image.parent
        image.decompose()
        if isinstance(parent, Tag) and not parent.get_text(strip=True) and not parent.find(["img", "table"]):
            parent.decompose()
    for note in list(soup.select(".source-note")):
        note.decompose()

    figure_html = (
        '<figure class="word-diagram" dir="ltr">'
        f'<img src="media/{visual.filename}" alt="{visual.alt}" loading="lazy" dir="ltr" />'
        '</figure>'
    )
    if key in {"2-1-1-karnaugh", "2-1-2-karnaugh"}:
        tables = soup.find_all("table")
        if not tables:
            raise SystemExit(f"Could not locate the Karnaugh-map table for visual {key}.")
        rendered_figure = BeautifulSoup(figure_html, "html.parser").find("figure")
        tables[-1].replace_with(rendered_figure)
        return str(soup).strip()
    return (str(soup).strip() + "\n" + figure_html).strip()


def build_grouped_exercise(
    children: List[Tag],
    spec: GroupedExerciseSpec,
    visuals: Dict[str, WordVisualSpec],
) -> dict:
    parts = []
    for part in spec.parts:
        part_spec = ExerciseSpec(
            number=f"{spec.number}{part.label}",
            section=spec.section,
            title=part.title,
            start=part.start,
            end=part.end,
            solution_start=part.solution_start,
            solution_marker=part.solution_marker,
            visual=part.visual,
        )
        question_html, solution_html = split_question_solution(children, part_spec)
        solution_html = attach_word_visual(solution_html, part.visual, visuals)
        if not question_html.strip():
            raise SystemExit(f"Empty question HTML for {spec.number} סעיף {part.label}")
        if not solution_html.strip():
            raise SystemExit(f"Empty solution HTML for {spec.number} סעיף {part.label}")
        parts.append({
            "label": part.label,
            "title": part.title,
            "questionHtml": question_html,
            "solutionHtml": solution_html,
        })

    intro_html = clean_fragment(children[spec.intro_start:spec.intro_end])
    if not intro_html.strip():
        intro_html = "<p>השאלה מחולקת לסעיפים. לכל סעיף פתרון שנפתח בנפרד.</p>"
    return {
        "id": exercise_id(spec.number),
        "number": spec.number,
        "section": spec.section,
        "title": spec.title,
        "questionHtml": intro_html,
        "parts": parts,
    }


def build_data(
    source: Path,
    html_path: Path,
    temp_dir: Path,
    docs_dir: Path,
) -> dict:
    raw_html = clean_raw_pandoc_html(html_path.read_text(encoding="utf-8"))
    soup = BeautifulSoup(raw_html, "html.parser")
    normalize_media(temp_dir, docs_dir, soup)
    postprocess_soup(soup)
    body = soup.body or soup
    children = [c for c in body.children if isinstance(c, Tag)]
    visuals = render_word_visuals(source, docs_dir, temp_dir)

    max_end = max(
        [spec.end for spec in EXERCISES]
        + [part.end for grouped in GROUPED_EXERCISES for part in grouped.parts]
    )
    if len(children) < max_end:
        raise SystemExit(f"Pandoc produced only {len(children)} top-level blocks, but the map expects at least {max_end}.")

    exercises = []
    build_items = (
        [(spec.start, "single", spec) for spec in EXERCISES]
        + [(spec.intro_start, "grouped", spec) for spec in GROUPED_EXERCISES]
    )
    for _, item_type, spec in sorted(build_items, key=lambda item: item[0]):
        if item_type == "grouped":
            exercises.append(build_grouped_exercise(children, spec, visuals))
            continue
        question_html, solution_html = split_question_solution(children, spec)
        solution_html = attach_word_visual(solution_html, spec.visual, visuals)
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
        "source": "private Word source (not included in the public repository)",
        "build": "pandoc-html-word-drawings-rtl-v11",
        "notes": "Public July 2026 edition. Chapters 1 and 5, Chapter 4 sections 4.1–4.7, and Chapter 2 logic questions are included; Chapter 3 remains a skeleton. Multi-part questions use a separate collapsible solution for every part. Word drawing canvases are rendered and content-trimmed automatically; no manual crop boxes are used.",
        "chapters": CHAPTERS,
        "exercises": exercises,
    }


def write_book_data(data: dict, docs_dir: Path) -> None:
    assets = docs_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    js = "window.BOOK_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
    (assets / "book-data.js").write_text(js, encoding="utf-8")


def prune_unused_media(data: dict, docs_dir: Path) -> None:
    """Do not publish media that is not referenced by the public book data."""
    media_dir = docs_dir / "media"
    serialized = json.dumps(data, ensure_ascii=False)
    referenced = set(re.findall(r"media/([^\"'\\]+)", serialized))
    for path in media_dir.iterdir():
        if path.is_file() and path.name not in referenced:
            path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Path to the private updated automation-book DOCX")
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
        data = build_data(source, html_path, temp_dir, docs_dir)
    prune_unused_media(data, docs_dir)
    write_book_data(data, docs_dir)
    print(f"Built {len(data['exercises'])} exercises from {source} into {docs_dir}")


if __name__ == "__main__":
    main()
