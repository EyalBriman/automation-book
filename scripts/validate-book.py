#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--docs", type=Path, default=Path("docs"))
args = parser.parse_args()
root = args.docs
errors: list[str] = []


def check_images(html: str, label: str) -> None:
    for src in re.findall(r'<img[^>]+src="([^"]+)"', html):
        path = root / src
        if not path.exists():
            errors.append(f"Missing image {src} in {label}")
        elif path.stat().st_size < 500:
            errors.append(f"Suspiciously small image {src} in {label}")


js_path = root / "assets" / "book-data.js"
if not js_path.exists():
    errors.append("Missing docs/assets/book-data.js")
    data = {"exercises": [], "chapters": []}
    raw = ""
else:
    raw = js_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw.removeprefix("window.BOOK_DATA = ").rstrip(" ;\n"))
    except Exception as exc:
        errors.append(f"Could not parse book-data.js: {exc}")
        data = {"exercises": [], "chapters": []}

exercises = data.get("exercises", [])
expected = set()
for section, count in [("1.1", 4), ("1.2", 4), ("1.3", 4), ("1.4", 8), ("1.5", 7)]:
    expected.update(f"{section}.{i}" for i in range(1, count + 1))
expected.update({"1.6.1א", "1.6.1ב", "1.6.2א", "1.6.2ב", "1.6.3"})
expected.update(f"1.7.{i}" for i in range(1, 6))
expected.update({"2.1.1", "2.1.2"})
expected.update(f"2.2.{i}" for i in range(1, 5))
expected.update(f"3.1.{i}" for i in range(1, 6))
expected.update({"3.2.1", "3.2.2"})
for section in range(1, 8):
    expected.update(f"4.{section}.{i}" for i in range(1, 4))
expected.update(f"5.{section}.1" for section in range(1, 6))

actual = {exercise.get("number") for exercise in exercises}
missing = sorted(expected - actual)
extra = sorted(actual - expected)
if missing:
    errors.append("Missing exercises: " + ", ".join(missing))
if extra:
    errors.append("Unexpected exercises: " + ", ".join(extra))
if len(exercises) != 76:
    errors.append(f"Expected 76 public exercises, found {len(exercises)}")

ids = [exercise.get("id") for exercise in exercises]
if len(ids) != len(set(ids)):
    errors.append("Exercise IDs are not unique")

expected_parts = {
    "1.7.1": list("אבגדהו"),
    "1.7.2": list("אבגדהו"),
    "1.7.3": list("אבגד"),
    "1.7.5": list("אבגדהו"),
    "5.1.1": list("אבגד"),
    "5.2.1": list("אבג"),
    "5.3.1": list("אבג"),
    "5.4.1": list("אבג"),
    "5.5.1": list("אבג"),
}

for exercise in exercises:
    number = exercise.get("number")
    question = exercise.get("questionHtml", "")
    solution = exercise.get("solutionHtml", "")
    if not question.strip():
        errors.append(f"Empty question: {number}")
    if "לא זוהה פתרון" in solution:
        errors.append(f"Unidentified solution: {number}")
    check_images(question + solution, str(number))

    parts = exercise.get("parts", [])
    if number in expected_parts:
        labels = [part.get("label") for part in parts]
        if labels != expected_parts[number]:
            errors.append(f"Wrong part labels for {number}: {labels}")
    elif parts:
        errors.append(f"Unexpected grouped parts in {number}")

    if parts:
        for part in parts:
            label = f"{number} סעיף {part.get('label')}"
            part_question = part.get("questionHtml", "")
            part_solution = part.get("solutionHtml", "")
            if not part_question.strip():
                errors.append(f"Empty part question: {label}")
            if not part_solution.strip():
                errors.append(f"Empty part solution: {label}")
            if "לא זוהה פתרון" in part_solution:
                errors.append(f"Unidentified part solution: {label}")
            check_images(part_question + part_solution, label)
    elif not solution.strip():
        errors.append(f"Empty solution: {number}")

source_notes = [exercise.get("number") for exercise in exercises if "source-note" in exercise.get("solutionHtml", "")]
allowed_source_notes = {"3.1.2"}
unexpected_source_notes = sorted(set(source_notes) - allowed_source_notes)
if unexpected_source_notes:
    errors.append(f"Unexpected missing-source solution notes: {unexpected_source_notes}")
if set(source_notes) != allowed_source_notes:
    errors.append(f"Expected a missing-source note only for 3.1.2, found: {source_notes}")

irrigation = next((exercise for exercise in exercises if exercise.get("number") == "2.1.1"), None)
if irrigation is None:
    errors.append("Missing irrigation-controller question 2.1.1")
else:
    irrigation_solution = irrigation.get("solutionHtml", "")
    for needle in ["תנאים להתחלת מחזור ההשקיה", "טבלת אמת עבור", "מפת קרנו עבור", "word-visual-2-1-1-karnaugh.png"]:
        if needle not in irrigation_solution:
            errors.append(f"2.1.1 solution is missing: {needle}")

required_visuals = [
    "word-visual-1-1-3-solution.png",
    "word-visual-1-7-1-d.png",
    "word-visual-1-7-2-d.png",
    "word-visual-1-7-3-b.png",
    "word-visual-1-7-4.png",
    "word-visual-1-7-5-c.png",
    "word-visual-2-1-1-karnaugh.png",
    "word-visual-2-1-2-karnaugh.png",
    "word-visual-2-2-1-fill-karnaugh.png",
    "word-visual-2-2-1-drain-karnaugh.png",
    "word-visual-2-2-1-light-karnaugh.png",
    "word-visual-2-2-2-karnaugh.png",
    "word-visual-2-2-3-karnaugh.png",
    "word-visual-5-2-a.png",
    "word-visual-5-3-c.png",
    "word-visual-5-5-c.png",
]
for filename in required_visuals:
    path = root / "media" / filename
    if not path.exists() or path.stat().st_size < 1000:
        errors.append(f"Missing or empty generated Word visual: {filename}")
    if filename not in raw:
        errors.append(f"Generated Word visual is not referenced: {filename}")

for legacy in ["1-7-1d-closed-loop.png", "1-1-3-kcl-circuit.png"]:
    if legacy in raw:
        errors.append(f"Legacy manual crop is still referenced: {legacy}")

if data.get("source") != "private Word source (not included in the public repository)":
    errors.append(f"Wrong source metadata: {data.get('source')}")
if "word-drawings" not in data.get("build", ""):
    errors.append("Build metadata does not identify the Word-drawing renderer")

chapter_status = {chapter.get("number"): chapter.get("status") for chapter in data.get("chapters", [])}
if chapter_status != {"1": "implemented", "2": "partial", "3": "partial", "4": "implemented", "5": "implemented"}:
    errors.append(f"Wrong chapter statuses: {chapter_status}")

if raw.count("word-code") < 5:
    errors.append("Arduino code blocks were not consistently marked LTR")

unpublished_section = "4." + str(8)
public_section_ids = {
    section.get("id")
    for chapter in data.get("chapters", [])
    for section in chapter.get("sections", [])
}
public_exercise_sections = {exercise.get("section") for exercise in exercises}
public_exercise_numbers = {exercise.get("number") for exercise in exercises}
if (
    unpublished_section in public_section_ids
    or unpublished_section in public_exercise_sections
    or any(str(number).startswith(unpublished_section + ".") for number in public_exercise_numbers)
):
    errors.append("Unpublished exam material is present in public book data")

referenced_media = set(re.findall(r"media/([^\"'\\]+)", raw))
actual_media = {path.name for path in (root / "media").iterdir() if path.is_file()}
unreferenced_media = sorted(actual_media - referenced_media)
if unreferenced_media:
    errors.append("Unreferenced media files are public: " + ", ".join(unreferenced_media))

index = root / "index.html"
if not index.exists():
    errors.append("Missing docs/index.html")
else:
    html = index.read_text(encoding="utf-8")
    for needle in ['dir="rtl"', "MathJax", "assets/book-data.js", "assets/app.js", "סעיפים 4.1–4.7"]:
        if needle not in html:
            errors.append(f"Missing {needle} in docs/index.html")

app = root / "assets" / "app.js"
if not app.exists():
    errors.append("Missing docs/assets/app.js")
else:
    app_html = app.read_text(encoding="utf-8")
    for needle in ["renderExerciseBody", "exercise-part", "solutionHtml"]:
        if needle not in app_html:
            errors.append(f"app.js is missing progressive-part support: {needle}")

css = root / "assets" / "styles.css"
if not css.exists():
    errors.append("Missing docs/assets/styles.css")
else:
    css_text = css.read_text(encoding="utf-8")
    for needle in [".formula-line", ".word-code", ".word-diagram", ".source-note"]:
        if needle not in css_text:
            errors.append(f"CSS is missing {needle}")

if errors:
    print("Validation failed:")
    for error in errors:
        print(" -", error)
    sys.exit(1)
print("Validation passed: 76 public exercises, generated Word visuals, and publication-safety checks are complete.")
