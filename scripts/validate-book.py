#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--docs', type=Path, default=Path('docs'))
args = parser.parse_args()
root = args.docs
errors = []
js_path = root / 'assets' / 'book-data.js'
if not js_path.exists():
    errors.append('Missing docs/assets/book-data.js')
else:
    raw = js_path.read_text(encoding='utf-8')
    try:
        data = json.loads(raw.removeprefix('window.BOOK_DATA = ').rstrip(' ;\n'))
    except Exception as exc:
        errors.append(f'Could not parse book-data.js: {exc}')
        data = {'exercises': []}
    exercises = data.get('exercises', [])
    expected = {
        '1.1.1','1.1.2','1.1.3','1.1.4',
        '1.2.1','1.2.2','1.2.3','1.2.4',
        '1.3.1','1.3.2','1.3.3','1.3.4',
        '1.4.1','1.4.2','1.4.3','1.4.4','1.4.5','1.4.6','1.4.7','1.4.8',
        '1.5.1','1.5.2','1.5.3','1.5.4','1.5.5','1.5.6','1.5.7',
        '1.6.1א','1.6.1ב','1.6.2א','1.6.2ב','1.6.3',
        '1.7.1','2.1.1','2.1.2'
    }
    actual = {e.get('number') for e in exercises}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing: errors.append('Missing exercises: ' + ', '.join(missing))
    if extra: errors.append('Unexpected exercises: ' + ', '.join(extra))

    def check_images(html: str, label: str):
        for src in re.findall(r'<img[^>]+src="([^"]+)"', html):
            if not (root / src).exists(): errors.append(f'Missing image {src} in {label}')

    for e in exercises:
        num = e.get('number')
        if not e.get('questionHtml', '').strip(): errors.append(f"Empty question: {num}")
        if 'לא זוהה פתרון' in e.get('solutionHtml', ''): errors.append(f"Unidentified solution: {num}")
        check_images(e.get('questionHtml','') + e.get('solutionHtml',''), str(num))
        if e.get('parts'):
            labels = [p.get('label') for p in e['parts']]
            if labels != ['א','ב','ג','ד','ה','ו']:
                errors.append(f"Review question parts are wrong: {labels}")
            for p in e['parts']:
                label = f"{num} סעיף {p.get('label')}"
                if not p.get('questionHtml','').strip(): errors.append(f"Empty part question: {label}")
                if not p.get('solutionHtml','').strip(): errors.append(f"Empty part solution: {label}")
                if 'לא זוהה פתרון' in p.get('solutionHtml',''): errors.append(f"Unidentified part solution: {label}")
                check_images(p.get('questionHtml','') + p.get('solutionHtml',''), label)
        else:
            if not e.get('solutionHtml', '').strip(): errors.append(f"Empty solution: {num}")
    if not any(e.get('number') == '1.7.1' and e.get('parts') for e in exercises):
        errors.append('1.7.1 is not rendered as one grouped review question with parts')

index = root / 'index.html'
if not index.exists(): errors.append('Missing docs/index.html')
else:
    html = index.read_text(encoding='utf-8')
    for needle in ['dir="rtl"', 'MathJax', 'assets/book-data.js', 'assets/app.js']:
        if needle not in html: errors.append(f'Missing {needle} in docs/index.html')
app = root / 'assets' / 'app.js'
if not app.exists(): errors.append('Missing docs/assets/app.js')
else:
    app_html = app.read_text(encoding='utf-8')
    if 'renderExerciseBody' not in app_html or 'exercise-part' not in app_html:
        errors.append('app.js does not support grouped exercise parts')
css = root / 'assets' / 'styles.css'
if not css.exists(): errors.append('Missing docs/assets/styles.css')
else:
    css_text = css.read_text(encoding='utf-8')
    if '.formula-line' not in css_text:
        errors.append('CSS is missing formula-line RTL/LTR fix')

if errors:
    print('Validation failed:')
    for err in errors:
        print(' -', err)
    sys.exit(1)
print('Validation passed.')
