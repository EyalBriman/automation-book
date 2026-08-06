# Course Manager Guide: Editing and Adding Questions

This guide is intended for a course manager who is not a programmer.

The short version is: **edit the Word file, rebuild the website, inspect the
result, and only then publish the generated public files.** Replacing or
uploading the Word file alone does not update the website.

## Canonical Word source

The default source file is:

`private-source/Automation_book4Aug2026.docx`

Create a backup before editing it. A new version can replace this file using
the same filename, or it can be kept elsewhere and passed to the build helper.

On Windows, a different DOCX file can simply be dragged onto
`BUILD_SITE_WINDOWS.bat`.

## Changing an existing word, number, formula, question, or solution

1. Open the canonical Word file.
2. Edit the existing content without deleting the question heading or its
   `פתרון` paragraph.
3. Save and close Microsoft Word.
4. Run the build helper.
5. Inspect the changed question, its solution, and the questions immediately
   before and after it.
6. Publish only after validation succeeds.

## Adding a new question

The safest method is to copy a complete question from the same section,
including its question heading, content, `פתרון` paragraph, and solution. Paste
it immediately after the last question in that section and replace its content.

This preserves the Word style, list level, and numbering structure recognized
by the importer.

### Chapters 1–3

1. Copy an entire existing question from the same section.
2. Paste it after the last question in that section.
3. Keep the question heading at the same multilevel-list level. Do not type a
   question number manually in a normal paragraph.
4. Replace the question content.
5. Keep a separate paragraph containing exactly `פתרון` or `פתרון:`.
6. Replace the solution content and save the document.

The public question number is generated from its position. For example, the
third question in section 3.2 becomes 3.2.3. This is how the mean-shift question
was added in the August 2026 version.

### Chapter 4

Copy a complete question block from the same section. Keep the heading pattern
`1)`, `2)`, `3)`, and update the number according to its position. Keep
`פתרון` in a separate paragraph.

Section 4.8 is intentionally excluded. Content placed in section 4.8 will not
appear on the public website.

### Chapter 5 and multi-part questions

Copy a complete exam or part using the same Word structure. Each new part
should be a numbered Word-list paragraph followed by a separate `פתרון`
paragraph. The website assigns the Hebrew part labels automatically.

Several existing exams contain historical formatting exceptions that the
importer already recognizes. New questions should use the regular structure
with an explicit solution paragraph for every part.

## When a question is not published

A question heading without a recognized solution paragraph is treated as a
draft and is not published. The two empty headings in section 3.3 currently use
this behavior.

Once real question content and a `פתרון` paragraph are added, the question will
be included in the next build.

## Images, tables, and diagrams

- For new images, use Word's **In Line with Text** wrapping option.
- Regular Word tables can be included in questions and solutions.
- A diagram made from many floating Word shapes may need to be flattened into
  one PNG image.
- If an image is missing from the generated website, do not publish. Save the
  diagram as PNG and insert it as an inline image.
- Some established Karnaugh maps and diagrams are also stored in
  `source/fixed-visuals` to guarantee stable output.

## RTL and LTR behavior

The Word file provides the text and document structure, but the website
controls directionality during the build:

- Hebrew paragraphs and tables are marked RTL.
- English text, variables, formulas, and Arduino code are isolated as LTR.
- Images receive fixed dimensions to prevent layout movement during loading.

No HTML or RTL code should be added to the Word file. After every update, check
parentheses, numbers, units, formulas, and English text in the browser.

## One-time installation on Windows

Install:

1. Python 3. During installation, select **Add Python to PATH**.
2. Pandoc.
3. LibreOffice Writer.
4. GitHub Desktop if a graphical Git workflow is preferred.

Restart Windows after installation.

## Building on Windows

1. Close Microsoft Word.
2. Double-click `BUILD_SITE_WINDOWS.bat` to use the bundled source, or drag a
   newer DOCX file onto it.
3. Wait for `BUILD AND VALIDATION SUCCEEDED`.
4. Inspect the website opened by the helper.

If an error appears, do not publish. Copy the complete error message and send
it to the technical maintainer.

## Building on macOS or Linux

After installing Python 3, Pandoc, and LibreOffice, run:

```bash
bash BUILD_SITE.sh
```

To build from another Word file:

```bash
bash BUILD_SITE.sh "/full/path/to/new-version.docx"
```

## Inspection checklist

Before publication, confirm that:

- The question number and title are correct.
- The question and solution were not reversed.
- All intended text, and only intended text, is public.
- Images, tables, Karnaugh maps, and diagrams appear correctly.
- Hebrew, English, numbers, and formulas appear in the correct order.
- Multi-part questions open one part at a time.
- Validation ends with `Validation passed`.
- No `.docx` file is included in the Git changes.

## Publishing

The included Bash helper can build, validate, and publish:

```bash
bash PUBLISH_TO_GITHUB.sh
```

The script excludes `private-source/` and all Word files from the public
repository.

GitHub Desktop can also be used: Fetch/Pull, run the build, verify that the
Word file is absent from the changes, Commit, and Push. There is no need to
upload a ZIP through the GitHub website.

## Receiving a new Word version

1. Keep a backup of the new DOCX file.
2. Confirm that new questions follow the structures described above.
3. Replace `private-source/Automation_book4Aug2026.docx`, or provide the new
   file path to the build helper.
4. Build and validate the website.
5. Manually inspect all new questions and section boundaries.
6. Publish the generated website and code, but never the Word source.

## Golden rule

Copy a complete template from the same section, keep `פתרון` in a separate
paragraph, rebuild, inspect, and only then publish.

