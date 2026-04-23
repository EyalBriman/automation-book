# Automation Course - Question Bank / מאגר שאלות לקורס אוטומציה

An interactive question and solution bank for an Automation and Integrated Systems course, built with [Quarto](https://quarto.org/).

**Live Site:** [Your GitHub Pages URL]

---

## 📚 Course Structure

The course covers 5 main topics:

1. **PLC & Logic** (PLC ולוגיקה) - PLCs, Ladder Diagrams, Boolean logic, timers, and counters
2. **Continuous Models & Control** (מודלים רציפים ובקרה) - Mechanical and electrical systems, transfer functions, PID controllers
3. **Sensing, Sensors, Communication & Actuators** (חישה, חיישנים, תקשורת ומפעילים) - Sensor specifications, motors, UART, measurement errors
4. **Arduino** (ארדואינו) - Arduino programming, PWM, sensors, libraries
5. **Computer Vision** (ראייה ממוחשבת) - Code implementation, segmentation, filters, Hough transform

---

## ⭐ Difficulty Levels

Questions in each topic are organized into three difficulty levels:

- **★ Practice Level** (רמת תרגול) - Basic questions for understanding core concepts and initial practice
- **★★ Medium Level** (רמת קושי בינונית) - More complex questions requiring integration of multiple concepts, suitable for exam preparation
- **★★★ Exam Level** (רמת מבחן) - Exam-level questions requiring deep thinking and complete mastery of material

---

## 🗂️ Repository Structure

```
automation-book-main/
├── index.qmd                    # Landing page (no navigation buttons)
├── _quarto.yml                  # Quarto configuration
├── README.md                    # This file
├── chapters/                    # Question chapters by topic
│   ├── plc.qmd                  # PLC & Logic (9 questions)
│   ├── models_control.qmd       # Continuous Models & Control
│   ├── sensors_actuators.qmd    # Sensing & Actuators
│   ├── arduino.qmd              # Arduino
│   └── cv.qmd                   # Computer Vision
├── images/                      # Images organized by topic
│   ├── PLC/                     # PLC ladder diagrams (19 images)
│   ├── models_control/          # (Future)
│   ├── sensors_actuators/       # (Future)
│   ├── arduino/                 # (Future)
│   └── cv/                      # (Future)
└── assets/                      # Styles, fonts, filters
    ├── styles.css
    ├── rtl-baseline.css         # RTL support for Hebrew
    ├── fonts.html
    ├── auto-env-titles.html
    └── env-to-callout.lua       # Quarto filter
```

---

## 🧭 Navigation

- **Landing page** (`index.qmd`) provides course overview and difficulty level explanations
- **Sidebar navigation** (left side) is the only way to navigate between topics
- No navigation buttons on the landing page - this is intentional to reduce confusion

---

## 📝 Question Format

Each question follows this structure:

```markdown
::: {.exercise}
**שאלה X.Y: Question Title**

[Question content in Hebrew]

1. Sub-question 1
2. Sub-question 2
...
:::

::: {.callout-note collapse="true" title="▸ הצג פתרון"}
[Solution content with step-by-step explanations]

**Mathematical notation:** Uses LaTeX with $...$ for inline and $$...$$ for display

**Images:** ![Description](../images/TOPIC/filename.png){width=X%}
:::
```

---

## 🚀 Building the Site

### Prerequisites
- [Quarto](https://quarto.org/docs/get-started/) installed

### Local Preview
```bash
quarto preview
```

### Build Static Site
```bash
quarto render
```

Output will be in the `docs/` folder (configured in `_quarto.yml`).

### Deploy to GitHub Pages
1. Push to GitHub
2. Go to repository Settings → Pages
3. Set source to: Deploy from branch `main` → folder `/docs`
4. Save

---

## ✏️ Adding New Questions

### To add questions to existing topics:

1. **Open the chapter file** (e.g., `chapters/plc.qmd`)
2. **Choose the difficulty section** (★, ★★, or ★★★)
3. **Add your question** using the format above
4. **Add images** to `images/[TOPIC]/` folder
5. **Update image references** in the question

### To add a new topic:

1. Create `chapters/new_topic.qmd`
2. Add to `_quarto.yml` under `chapters:`
3. Create `images/new_topic/` folder
4. Follow the 3-level difficulty structure

---

## 🎨 Styling

- **RTL Support:** Hebrew text is automatically rendered right-to-left
- **Custom Styles:** Defined in `assets/styles.css`
- **Collapsible Solutions:** Uses Quarto callout blocks with `collapse="true"`

---

## 📊 Current Progress

| Topic | Questions | Images | Status |
|-------|-----------|--------|--------|
| PLC & Logic | 9 | 19 | ✅ Complete |
| Models & Control | TBD | TBD | 🚧 In Progress |
| Sensors & Actuators | TBD | TBD | 🚧 In Progress |
| Arduino | TBD | TBD | 🚧 In Progress |
| Computer Vision | TBD | TBD | 🚧 In Progress |

---

## 📄 License

This work is licensed under a [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-nc-sa/4.0/).

**This means you are free to:**
- **Share** — copy and redistribute the material in any medium or format
- **Adapt** — remix, transform, and build upon the material

**Under the following terms:**
- **Attribution** — You must give appropriate credit, provide a link to the license, and indicate if changes were made
- **NonCommercial** — You may not use the material for commercial purposes
- **ShareAlike** — If you remix, transform, or build upon the material, you must distribute your contributions under the same license

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](http://creativecommons.org/licenses/by-nc-sa/4.0/)

---

## 👥 Contributors

**Course Development Team:**
- **Eyal Briman**
- **Sigal Berman**

---

## 🐛 Issues & Contributions

Found a bug or want to contribute? [Open an issue](../../issues) or submit a pull request!

---

**Built with ❤️ using [Quarto](https://quarto.org/)**
