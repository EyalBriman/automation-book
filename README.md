# ספר תרגילים באוטומציה ומערכות משולבות

הפרויקט בונה אתר GitHub Pages מתוך מסמך Word ראשי. גרסת המקור המצורפת למסירה
היא `private-source/Automation_book4Aug2026.docx`, והיא כבר נבנתה לאתר שבתיקייה
`docs/`.

הבנייה הנוכחית מזהה שאלות לפי מבנה המסמך ולא לפי מספרי שורות או מיקומי Pandoc
קבועים. לכן אפשר להוסיף שאלה חדשה באותו מבנה של השאלות הסמוכות, להוסיף פסקת
`פתרון`, ולבנות מחדש.

## התחלה מהירה

Windows: לחיצה כפולה על `BUILD_SITE_WINDOWS.bat`. אפשר גם לגרור עליו קובץ Word
חדש יותר.

macOS או Linux:

```bash
bash BUILD_SITE.sh
```

לאחר בדיקה בדפדפן, פרסום ב־GitHub:

```bash
bash PUBLISH_TO_GITHUB.sh
```

ברירת המחדל של סקריפט הפרסום היא
`https://github.com/EyalBriman/automation-book.git`. למאגר אחר:

```bash
REPO_URL="https://github.com/USER/REPOSITORY.git" bash PUBLISH_TO_GITHUB.sh
```

## תוכנות נדרשות

- Python 3.10 ומעלה.
- Pandoc.
- LibreOffice Writer.
- Git ו־rsync רק עבור `PUBLISH_TO_GITHUB.sh`.
- חבילות Python מתוך `requirements.txt`; סקריפט הבנייה מתקין אותן אוטומטית.

## מה נוצר

- `docs/` — האתר המוכן לפרסום.
- `docs/assets/book-data.js` — השאלות, הפתרונות ומבנה הספר.
- `docs/media/` — התמונות והשרטוטים שהאתר משתמש בהם בפועל.

קובץ ה־Word אינו נטען ישירות בדפדפן. בכל שינוי צריך להריץ בנייה מחדש. כיוון
העמוד מוגדר RTL באתר; עברית נשארת RTL, ואנגלית, נוסחאות וקוד מבודדים כ־LTR.

## פקודות ידניות

```bash
python3 -m pip install -r requirements.txt
python3 scripts/build-from-word-semantic.py \
  private-source/Automation_book4Aug2026.docx --out docs
python3 scripts/validate-book.py --docs docs
```

## פרטיות ופרסום

קובצי `.docx` מוחרגים מ־Git. סקריפט הפרסום גם מוחרג במפורש את
`private-source/` ואת כל קובצי ה־Word, ולכן המקור והפתרונות הפרטיים אינם
נשלחים למאגר הציבורי. הקובץ נשאר בתוך ZIP המסירה לצורך העדכון הבא.

הוראות מדויקות לעריכת שאלה, הוספת שאלה ובדיקת התוצאה נמצאות ב־
[מדריך למנהל הקורס](COURSE_MANAGER_GUIDE_HE.md).

## כללי פרסום נוכחיים

- גרסת August 2026 מפרסמת 77 שאלות, כולל שאלה 3.2.3 על mean shift.
- הכותרות הריקות ב־3.3 נשארות במצב מתוכנן עד שיופיעו תחתיהן שאלה ופתרון.
- סעיף 4.8 אינו מפורסם בכוונה.
- הכותרות הכפולות בפרק 5 מוצגות באתר כרצף 5.1–5.5.

