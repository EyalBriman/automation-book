# Automation and Integrated Systems Exercise Book

This project builds a Hebrew GitHub Pages exercise book from a canonical Word
document. The source version included in this handoff is:

`private-source/Automation_book4Aug2026.docx`

The generated, publishable website is already available in `docs/`.

The current importer discovers chapters, sections, questions, and solutions
from the Word document structure. It no longer depends on fixed Pandoc block
positions. A manager can therefore add a question by copying the structure of
a nearby question, adding a separate `פתרון` paragraph, and rebuilding the
site.

## Quick start

On Windows, double-click `BUILD_SITE_WINDOWS.bat`. A newer Word file can also
be dragged onto that file.

On macOS or Linux:

```bash
bash BUILD_SITE.sh
```

After checking the generated site, publish it with:

```bash
bash PUBLISH_TO_GITHUB.sh
```

The default repository is:

`https://github.com/EyalBriman/automation-book.git`

To use another repository:

```bash
REPO_URL="https://github.com/USER/REPOSITORY.git" bash PUBLISH_TO_GITHUB.sh
```

## Required software

- Python 3.10 or newer.
- Pandoc.
- LibreOffice Writer.
- Git and `rsync` for `PUBLISH_TO_GITHUB.sh`.
- The Python packages listed in `requirements.txt`.

The build helpers install or check the Python packages automatically.

## Generated files

- `docs/` contains the complete public website.
- `docs/assets/book-data.js` contains the generated book structure, questions,
  and solutions.
- `docs/media/` contains only images referenced by the public website.

The browser does not read the Word file directly. Every Word change requires a
new build and validation run.

The website controls text direction: Hebrew paragraphs use RTL, while English,
mathematical expressions, variables, and Arduino code are isolated as LTR.

## Manual build commands

```bash
python3 -m pip install -r requirements.txt
python3 scripts/build-from-word-semantic.py \
  private-source/Automation_book4Aug2026.docx --out docs
python3 scripts/validate-book.py --docs docs
```

## Privacy and publication safety

All `.docx` files and the complete `private-source/` directory are ignored by
Git. The publishing script also explicitly excludes Word files and the private
source directory.

The source Word document is included in the handoff ZIP so that the course
manager can prepare the next version. It must not be uploaded to the public
GitHub repository.

See [COURSE_MANAGER_GUIDE.md](COURSE_MANAGER_GUIDE.md) for the complete editing,
building, checking, and publication procedure.

## Current publication rules

- The August 2026 build publishes 77 questions, including the new mean-shift
  question 3.2.3.
- The two empty question headings in section 3.3 remain drafts until they have
  complete question and solution content.
- Section 4.8 is intentionally excluded from publication.
- Duplicate exam headings in chapter 5 are published sequentially as sections
  5.1 through 5.5.

