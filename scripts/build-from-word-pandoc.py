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
    additional_visuals: Sequence[str] = ()


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
    replace_table_index: Optional[int] = None


# Explicit semantic map for Automation_book23July2026.docx. The Word file does
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

    ExerciseSpec("1.7.4", "1.7", "בקרת מהירות לרכב", 1131, 1171, solution_start=1135, visual="1-7-4"),

    # Chapter 2. The reactor example is numbered 2.2.1 in the Word source and
    # is placed before the two logic exercises; it is grouped under section 2.2
    # here so exercise identifiers remain unique and the chapter navigation is coherent.
    ExerciseSpec(
        "2.2.1",
        "2.2",
        "בקרת ראקטור – מוני זמן",
        1219,
        1236,
        solution_start=1220,
        solution_marker=False,
        visual="2-2-1-fill-karnaugh",
        additional_visuals=("2-2-1-drain-karnaugh", "2-2-1-light-karnaugh"),
    ),
    ExerciseSpec("2.1.1", "2.1", "בקר השקייה", 1236, 1251, solution_start=1238, visual="2-1-1-karnaugh"),
    ExerciseSpec("2.1.2", "2.1", "בקר למקרר תעשייתי", 1251, 1265, solution_start=1254, visual="2-1-2-karnaugh"),
    ExerciseSpec("2.2.2", "2.2", "הפעלת חניון – מוני זמן", 1266, 1283, solution_start=1268, visual="2-2-2-karnaugh"),
    ExerciseSpec("2.2.3", "2.2", "מערכת האכלת כלב – רגיסטרים", 1284, 1311, solution_start=1286, visual="2-2-3-karnaugh"),
    ExerciseSpec("2.2.4", "2.2", "מערכת בקרת אקלים – רגיסטרים", 1312, 1335, solution_start=1314),

    # Chapter 3. The Word numbering restarts inside section 3.1; the website
    # continues the sequence so every public exercise has a stable unique id.
    ExerciseSpec("3.1.1", "3.1", "תמונת VALUE ומסנן חידוד", 1336, 1346, solution_start=1343),
    ExerciseSpec("3.1.2", "3.1", "סגמנטציה ידנית בעזרת K-means", 1346, 1350, solution_start=1349),
    ExerciseSpec("3.1.3", "3.1", "תמונת רמות אפור והמרה לשחור־לבן", 1350, 1379, solution_start=1367),
    ExerciseSpec("3.1.4", "3.1", "מלבן, מרכז כובד ומורפולוגיה", 1379, 1401, solution_start=1387),
    ExerciseSpec("3.1.5", "3.1", "סף, מרכז כובד ומסנן קצוות", 1401, 1427, solution_start=1406),
    ExerciseSpec("3.2.1", "3.2", "סגמנטציה בעזרת K-means", 1427, 1444, solution_start=1431),
    ExerciseSpec("3.2.2", "3.2", "סגמנטציית קוביות בעזרת K-means", 1444, 1462, solution_start=1452),

    ExerciseSpec("4.1.1", "4.1", "שגיאה מוחלטת ושגיאה יחסית", 1464, 1483, solution_start=1470),
    ExerciseSpec("4.1.2", "4.1", "ממוצע מדידות וחזרתיות", 1483, 1500, solution_start=1489),
    ExerciseSpec("4.1.3", "4.1", "מערכת מדידה עם המרה ליניארית", 1500, 1519, solution_start=1507),
    ExerciseSpec("4.2.1", "4.2", "תחום, טווח ו־FSD", 1520, 1541, solution_start=1528),
    ExerciseSpec("4.2.2", "4.2", "רזולוציה של חיישן", 1541, 1562, solution_start=1551),
    ExerciseSpec("4.2.3", "4.2", "לינאריות ושגיאת אי־לינאריות", 1562, 1593, solution_start=1572),
    ExerciseSpec("4.3.1", "4.3", "רזולוציית ממיר A/D", 1594, 1602, solution_start=1597),
    ExerciseSpec("4.3.2", "4.3", "קצב דגימה מינימלי", 1602, 1611, solution_start=1605),
    ExerciseSpec("4.3.3", "4.3", "כמות דגימות", 1611, 1620, solution_start=1614),
    ExerciseSpec("4.4.1", "4.4", "תיקון Offset", 1621, 1643, solution_start=1630),
    ExerciseSpec("4.4.2", "4.4", "מציאת קבוע כיול", 1643, 1662, solution_start=1652),
    ExerciseSpec("4.4.3", "4.4", "עקומת כיול ליניארית", 1662, 1690, solution_start=1672),
    ExerciseSpec("4.5.1", "4.5", "PWM ומתח ממוצע", 1691, 1700, solution_start=1695),
    ExerciseSpec("4.5.2", "4.5", "מהירות מנוע כתלות ב־PWM", 1700, 1713, solution_start=1705),
    ExerciseSpec("4.5.3", "4.5", "מומנט נדרש להרמת עומס", 1713, 1727, solution_start=1719),
    ExerciseSpec("4.6.1", "4.6", "הספק מכני של מנוע", 1728, 1738, solution_start=1731),
    ExerciseSpec("4.6.2", "4.6", "מנוע Stepper ותנועה קווית", 1738, 1747, solution_start=1742),
    ExerciseSpec("4.6.3", "4.6", "מנוע סרוו וזווית פקודה", 1747, 1765, solution_start=1754),
    ExerciseSpec("4.7.1", "4.7", "רזולוציה של אנקודר אינקרמנטלי", 1766, 1776, solution_start=1770),
    ExerciseSpec("4.7.2", "4.7", "אנקודר קוואדרטי", 1776, 1789, solution_start=1780),
    ExerciseSpec("4.7.3", "4.7", "מרחק נסיעה לפי ספירות אנקודר", 1789, 1806, solution_start=1794),
]

GROUPED_EXERCISES: List[GroupedExerciseSpec] = [
    GroupedExerciseSpec("1.7.1", "1.7", "מועד א׳ 2026 סמסטר א", 944, 948, [
        PartSpec("א", "פיזיקליות ויציבות", 948, 967, solution_start=950),
        PartSpec("ב", "ערכי מצב מתמיד", 967, 985, solution_start=971),
        PartSpec("ג", "מרחב מצבים", 985, 991, solution_start=986, solution_marker=False),
        PartSpec("ד", "דיאגרמת חוג סגור", 991, 994, solution_start=993, visual="1-7-1-d"),
        PartSpec("ה", "תמסורות חוג פתוח וסגור", 994, 1002, solution_start=995, solution_marker=False),
        PartSpec("ו", "מוצאי חוג פתוח וסגור", 1002, 1018, solution_start=1006),
    ]),
    GroupedExerciseSpec("1.7.2", "1.7", "מועד א׳ 2025 סמסטר ב", 1018, 1021, [
        PartSpec("א", "מודל מרחב המצבים", 1021, 1027, solution_start=1022),
        PartSpec("ב", "פיזיקליות ויציבות", 1027, 1043, solution_start=1028),
        PartSpec("ג", "ערך מצב מתמיד", 1043, 1046, solution_start=1044),
        PartSpec("ד", "דיאגרמת חוג סגור", 1046, 1049, solution_start=1047, visual="1-7-2-d"),
        PartSpec("ה", "תמסורת חוג סגור", 1049, 1056, solution_start=1050),
        PartSpec("ו", "תחומי יציבות ופיזיקליות", 1056, 1068, solution_start=1059),
    ]),
    GroupedExerciseSpec("1.7.3", "1.7", "מועד א׳ 2025 סמסטר א", 1068, 1072, [
        PartSpec("א", "פיזיקליות ויציבות", 1072, 1107, solution_start=1073),
        PartSpec("ב", "תמסורת חוג סגור", 1107, 1113, solution_start=1109, visual="1-7-3-b"),
        PartSpec("ג", "תחום קבוע הבקרה", 1113, 1124, solution_start=1115),
        PartSpec("ד", "ערכי מצב מתמיד", 1124, 1131, solution_start=1125),
    ]),
    GroupedExerciseSpec("1.7.5", "1.7", "מועד א׳ 2024 סמסטר ב", 1171, 1174, [
        PartSpec("א", "יציבות התהליך", 1174, 1181, solution_start=1176),
        PartSpec("ב", "תגובה למדרגה", 1181, 1197, solution_start=1183),
        PartSpec("ג", "דיאגרמת חוג סגור", 1197, 1199, solution_start=1198, solution_marker=False, visual="1-7-5-c"),
        PartSpec("ד", "תמסורת חוג סגור", 1199, 1202, solution_start=1200),
        PartSpec("ה", "תחום קבוע הבקרה", 1202, 1209, solution_start=1204),
        PartSpec("ו", "ריסון קריטי", 1209, 1215, solution_start=1211, solution_marker=False),
    ]),
    GroupedExerciseSpec("5.1.1", "5.1", "מועד א׳ 2026 סמסטר א", 1944, 1947, [
        PartSpec("א", "משתנה lastVal", 1947, 1950, solution_start=1948),
        PartSpec("ב", "פעולת נורת ה־LED", 1950, 1953, solution_start=1951),
        PartSpec("ג", "פיצול הטיפול בנורה", 1953, 1956, solution_start=1954),
        PartSpec("ד", "חיבור הרכיבים", 1956, 1966, solution_start=1963),
    ]),
    GroupedExerciseSpec("5.2.1", "5.2", "מועד א׳ 2025 סמסטר ב", 1966, 1971, [
        PartSpec("א", "המערכת כחיישן", 1971, 1974, solution_start=1972, visual="5-2-a"),
        PartSpec("ב", "פעולת הקוד", 1974, 1990, solution_start=1975),
        PartSpec("ג", "חיבור הרכיבים", 1990, 1993, solution_start=1991, solution_marker=False),
    ]),
    GroupedExerciseSpec("5.3.1", "5.3", "מועד א׳ 2025 סמסטר א", 1993, 1996, [
        PartSpec("א", "המערכת כחיישן", 1996, 2001, solution_start=1997),
        PartSpec("ב", "פעולת הקוד ותיקונו", 2001, 2016, solution_start=2002),
        PartSpec("ג", "חיבור הרכיבים", 2016, 2023, solution_start=2017, visual="5-3-c"),
    ]),
    GroupedExerciseSpec("5.4.1", "5.4", "מועד א׳ 2024 סמסטר ב", 2023, 2026, [
        PartSpec("א", "תיקון שגיאות בקוד", 2026, 2031, solution_start=2027),
        PartSpec("ב", "פונקציית Ginput", 2031, 2037, solution_start=2032),
        PartSpec("ג", "שינוי הגדרות הפינים", 2037, 2040, solution_start=2038),
    ]),
    GroupedExerciseSpec("5.5.1", "5.5", "מועד א׳ 2024 סמסטר א", 2040, 2043, [
        PartSpec("א", "תפקיד הארדואינו", 2043, 2046, solution_start=2044),
        PartSpec("ב", "פעולת הקוד", 2046, 2054, solution_start=2047),
        PartSpec("ג", "חיבור הרכיבים", 2054, 2058, solution_start=2055, visual="5-5-c"),
    ]),
]


WORD_VISUALS: List[WordVisualSpec] = [
    WordVisualSpec("1-1-3-solution", "word-visual-1-1-3-solution.png", [63], "מעגל חשמלי עם סימון הזרמים עבור פתרון שאלה 1.1.3"),
    WordVisualSpec("1-7-1-d", "word-visual-1-7-1-d.png", list(range(1124, 1129)), "דיאגרמת החוג הסגור עבור מועד א׳ 2026, סעיף ד"),
    WordVisualSpec("1-7-2-d", "word-visual-1-7-2-d.png", list(range(1209, 1213)), "דיאגרמת החוג הסגור עבור מועד א׳ 2025 סמסטר ב, סעיף ד"),
    WordVisualSpec("1-7-3-b", "word-visual-1-7-3-b.png", list(range(1302, 1306)), "דיאגרמת החוג הסגור עבור מועד א׳ 2025 סמסטר א, סעיף ב"),
    WordVisualSpec("1-7-4", "word-visual-1-7-4.png", list(range(1378, 1382)), "דיאגרמת חוג סגור של מערכת בקרת מהירות לרכב"),
    WordVisualSpec("1-7-5-c", "word-visual-1-7-5-c.png", [1462, 1463, 1464, 1465, 1467], "דיאגרמת החוג הסגור עבור מועד א׳ 2024 סמסטר ב, סעיף ג"),
    WordVisualSpec(
        "2-2-1-fill-karnaugh",
        "word-visual-2-2-1-fill-karnaugh.png",
        [],
        "מפת קרנו צבעונית עבור מנוע המילוי בבקרת הראקטור",
        body_elements=[1516],
        replace_table_index=2,
    ),
    WordVisualSpec(
        "2-2-1-drain-karnaugh",
        "word-visual-2-2-1-drain-karnaugh.png",
        [],
        "מפת קרנו צבעונית עבור ניקוז הראקטור",
        body_elements=[1523],
        replace_table_index=4,
    ),
    WordVisualSpec(
        "2-2-1-light-karnaugh",
        "word-visual-2-2-1-light-karnaugh.png",
        [],
        "מפת קרנו צבעונית עבור נורת החיווי בבקרת הראקטור",
        body_elements=[1533],
        replace_table_index=6,
    ),
    WordVisualSpec(
        "2-1-1-karnaugh",
        "word-visual-2-1-1-karnaugh.png",
        [],
        "מפת קרנו צבעונית עבור בקר ההשקיה",
        body_elements=[1561],
        replace_table_index=2,
    ),
    WordVisualSpec(
        "2-1-2-karnaugh",
        "word-visual-2-1-2-karnaugh.png",
        [],
        "מפת קרנו צבעונית עבור בקר המקרר התעשייתי",
        body_elements=[1591],
        replace_table_index=2,
    ),
    WordVisualSpec(
        "2-2-2-karnaugh",
        "word-visual-2-2-2-karnaugh.png",
        [],
        "מפת קרנו צבעונית עבור מנוע שער החניון",
        body_elements=[1621],
        replace_table_index=2,
    ),
    WordVisualSpec(
        "2-2-3-karnaugh",
        "word-visual-2-2-3-karnaugh.png",
        [],
        "מפת קרנו צבעונית עבור פקד הברז במערכת האכלת הכלב",
        body_elements=[1670],
        replace_table_index=2,
    ),
    WordVisualSpec("5-2-a", "word-visual-5-2-a.png", [2609, 2610], "שרשרת האותות של המערכת האולטרסונית"),
    WordVisualSpec("5-3-c", "word-visual-5-3-c.png", list(range(2745, 2757)), "חיבור ארדואינו, מטריצת חיבורים, מיקרופון ונורות"),
    WordVisualSpec("5-5-c", "word-visual-5-5-c.png", [2885, 2887], "חיבור ארדואינו למנורת שולחן ולכפתור קפיצי"),
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
            {"id": "2.1", "title": "לוגיקה"},
            {"id": "2.2", "title": "בקרים"},
            {"id": "2.3", "title": "שאלות חזרה", "comingSoon": True},
        ],
    },
    {
        "id": "chapter-3",
        "number": "3",
        "title": "עיבוד תמונה",
        "status": "partial",
        "sections": [
            {"id": "3.1", "title": "סינון"},
            {"id": "3.2", "title": "סגמנטציה"},
            {"id": "3.3", "title": "מאפיינים", "comingSoon": True},
            {"id": "3.4", "title": "שאלות חזרה", "comingSoon": True},
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




def attach_word_visuals(
    solution_html: str,
    keys: Sequence[str],
    visuals: Dict[str, WordVisualSpec],
) -> str:
    if not keys:
        return solution_html
    selected: List[WordVisualSpec] = []
    for key in keys:
        visual = visuals.get(key)
        if visual is None:
            raise SystemExit(f"Unknown Word visual key: {key}")
        selected.append(visual)

    soup = BeautifulSoup(solution_html, "html.parser")

    # Replace drawing-over-table canvases from the last table backwards, keeping
    # ordinary Word/Pandoc images elsewhere in the same solution.
    table_visuals = sorted(
        (visual for visual in selected if visual.replace_table_index is not None),
        key=lambda visual: int(visual.replace_table_index or 0),
        reverse=True,
    )
    for visual in table_visuals:
        tables = soup.find_all("table")
        table_index = int(visual.replace_table_index or 0)
        if table_index >= len(tables):
            raise SystemExit(
                f"Could not locate table {table_index} for generated visual {visual.key}; "
                f"the solution contains {len(tables)} tables."
            )
        figure_html = (
            '<figure class="word-diagram" dir="ltr">'
            f'<img src="media/{visual.filename}" alt="{visual.alt}" loading="lazy" dir="ltr" />'
            '</figure>'
        )
        rendered_figure = BeautifulSoup(figure_html, "html.parser").find("figure")
        tables[table_index].replace_with(rendered_figure)

    append_visuals = [visual for visual in selected if visual.replace_table_index is None]
    if append_visuals:
        # An appended image is the complete drawing canvas. Remove Pandoc's
        # partial fragments so connectors and labels are not duplicated.
        for image in list(soup.find_all("img")):
            parent = image.parent
            image.decompose()
            if isinstance(parent, Tag) and not parent.get_text(strip=True) and not parent.find(["img", "table"]):
                parent.decompose()
        for note in list(soup.select(".source-note")):
            note.decompose()
        for visual in append_visuals:
            figure_html = (
                '<figure class="word-diagram" dir="ltr">'
                f'<img src="media/{visual.filename}" alt="{visual.alt}" loading="lazy" dir="ltr" />'
                '</figure>'
            )
            soup.append(BeautifulSoup(figure_html, "html.parser"))
    return str(soup).strip()


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
        solution_html = attach_word_visuals(
            solution_html,
            [part.visual] if part.visual else [],
            visuals,
        )
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
        visual_keys = ([spec.visual] if spec.visual else []) + list(spec.additional_visuals)
        solution_html = attach_word_visuals(solution_html, visual_keys, visuals)
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
        "build": "pandoc-html-word-drawings-rtl-v12",
        "notes": "Public 23 July 2026 edition. Chapters 1 and 5, Chapter 2 sections 2.1–2.2, Chapter 3 sections 3.1–3.2, and Chapter 4 sections 4.1–4.7 are included. Unpublished source material remains excluded. Multi-part exam questions use a separate collapsible solution for every part. Word drawing canvases are rendered and content-trimmed automatically; no manual crop boxes are used.",
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
