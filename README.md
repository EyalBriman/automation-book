# Automation and Integrated Systems Exercise Book

This project builds a Hebrew GitHub Pages exercise book from a canonical Word
document. The default private source path is:

`private-source/Automation_book_current.docx`

This complete handoff includes the current private Word source at that path, so
`BUILD_SITE_WINDOWS.bat` can be started by double-clicking it. A newer `.docx`
can instead be dragged onto the helper.

For the included BAT test, `docs/` intentionally contains the 77-question
starting website. It is not the final publishable version yet. Run the Windows
helper successfully first; it will generate the 78-question website from the
included Word source.

The current importer discovers chapters, sections, questions, and solutions
from the Word document structure. It no longer depends on fixed Pandoc block
positions. A manager can therefore edit a question in place, add a question by
copying nearby structure, or remove a question from the public site by leaving
its styled heading as an empty draft. Every published solution uses a separate
`פתרון` paragraph. The question's Word list is the source of truth for its
parts. A question may use Hebrew `א, ב, ג` or numeric `1, 2, 3`; the importer
uses the same scheme and the same number of labels in its solution. This works
both when every part is followed by its solution and when all answers are
collected at the end. Supporting lists inside an answer are not treated as
additional parts.

## Quick start

On Windows, double-click `BUILD_SITE_WINDOWS.bat`. A newer Word file can also
be dragged onto that file. The helper always rebuilds the complete website from
the selected Word file, prints an informational question-change summary, and
only replaces `docs/` after the staged build passes validation.

### Included BAT test

This package deliberately starts with 77 questions in `docs/`, while the
included Word source contains question 2.2.5. This lets a manager test the real
Word-to-website workflow instead of receiving a site that was already built.

1. Double-click `BUILD_SITE_WINDOWS.bat`.
2. Wait for the complete rebuild and the change summary.
3. The summary should say `Added public numbers: 2.2.5` and no removed public
   numbers. It also reports 1.2.2–1.2.4 and 1.3.2–1.3.4 as changed because this
   build corrects their solution labels from Hebrew letters to the numeric
   scheme used by their Word questions.
4. Continue only if the window ends with `BUILD AND VALIDATION SUCCEEDED` and
   the opened website contains 2.2.5 with Hebrew parts א–ד. In its solution,
   the condition lines inside answer א must be bullets, not another א–ד list.

After this test succeeds, the local `docs/` folder contains 78 questions and
is ready to publish. Running the BAT again simply rebuilds and validates the
complete site again.

The change summary is informational and compares normalized visible wording.
The full validator and the opened browser preview remain the checks for images,
tables, list numbering, subparts, and page behavior.

On macOS or Linux:

```bash
bash BUILD_SITE.sh
```

After checking the generated site, publish it with an explicit repository URL:

```bash
REPO_URL="https://github.com/CURRENT_OWNER/automation-book.git" \
  SKIP_BUILD=1 \
  bash PUBLISH_TO_GITHUB.sh
```

On Windows, after `BUILD_SITE_WINDOWS.bat` has already ended with
`BUILD AND VALIDATION SUCCEEDED`, open Git Bash in the project folder and use:

```bash
REPO_URL="https://github.com/CURRENT_OWNER/automation-book.git" \
  SKIP_BUILD=1 \
  bash PUBLISH_TO_GITHUB.sh
```

This uploads the existing, already-validated generated site without trying to
run Python, Pandoc, or LibreOffice a second time inside Git Bash.

The publishing script deliberately requires `REPO_URL`. Use `EyalBriman` as
`CURRENT_OWNER` while the repository is still under Eyal, or `Bermansi` after
the transfer is complete.

To use another repository:

```bash
REPO_URL="https://github.com/OWNER/automation-book.git" \
  SKIP_BUILD=1 \
  COMMIT_MESSAGE="Add question 2.2.5 and fix Hebrew subparts" \
  bash PUBLISH_TO_GITHUB.sh
```

## Required software

- Python 3.10 or newer.
- Pandoc.
- LibreOffice Writer.
- Git for Windows, which includes Git Bash, for `PUBLISH_TO_GITHUB.sh`.
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
  private-source/Automation_book_current.docx --out docs
python3 scripts/validate-book.py --docs docs
```

## Privacy and publication safety

All `.docx` files and the complete `private-source/` directory are ignored by
Git. The publishing script also explicitly excludes Word files and the private
source directory.

The Word source is included in this handoff ZIP for local course management.
It is ignored by Git and excluded by the publishing script, so it is not
uploaded to the public GitHub repository.

See [COURSE_MANAGER_GUIDE.md](COURSE_MANAGER_GUIDE.md) for the complete editing,
building, checking, and publication procedure.

## Current publication rules

- After the included BAT test succeeds, the September 2026 build publishes 78
  questions, including question 2.2.5 and the mean-shift question 3.2.3.
- The two empty question headings in section 3.3 remain drafts until they have
  complete question and solution content.
- Section 4.8 is intentionally excluded from publication.
- Duplicate exam headings in chapter 5 are published sequentially as sections
  5.1 through 5.5.
