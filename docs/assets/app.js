(function () {
  function sectionTitle(id) {
    for (const chapter of window.BOOK_DATA.chapters) {
      for (const section of chapter.sections || []) {
        if (section.id === id) return `${section.id} ${section.title}`;
      }
    }
    return id;
  }

  function renderPlan() {
    const grid = document.getElementById('plan-grid');
    grid.innerHTML = '';
    for (const chapter of window.BOOK_DATA.chapters) {
      const card = document.createElement('article');
      card.className = 'plan-card';
      const badgeText = chapter.status === 'implemented' ? 'ממומש' : chapter.status === 'partial' ? 'חלקי' : 'שלד';
      const badgeClass = chapter.status === 'implemented' ? 'badge' : 'badge badge-muted';
      card.innerHTML = `
        <h3>פרק ${chapter.number} ${chapter.title} <span class="${badgeClass}">${badgeText}</span></h3>
        <ul>${(chapter.sections || []).map(s => `<li>${s.id} ${s.title}${s.comingSoon ? ' <span class="badge badge-muted">בעבודה</span>' : ''}</li>`).join('')}</ul>
      `;
      grid.appendChild(card);
    }
  }

  function renderNav() {
    const nav = document.getElementById('book-nav');
    nav.innerHTML = '';
    for (const chapter of window.BOOK_DATA.chapters) {
      const wrap = document.createElement('div');
      wrap.className = 'nav-chapter';
      wrap.innerHTML = `<div class="nav-chapter-title">פרק ${chapter.number} ${chapter.title}</div>`;
      for (const section of chapter.sections || []) {
        const sectionExercises = window.BOOK_DATA.exercises.filter(e => e.section === section.id);
        const sectionLink = document.createElement(sectionExercises.length ? 'a' : 'div');
        sectionLink.className = sectionExercises.length ? 'nav-section' : 'nav-coming';
        sectionLink.textContent = `${section.id} ${section.title}` + (section.comingSoon ? ' · בעבודה' : '');
        if (sectionExercises.length) sectionLink.href = `#section-${section.id.replaceAll('.', '-')}`;
        wrap.appendChild(sectionLink);
        for (const ex of sectionExercises) {
          const a = document.createElement('a');
          a.className = 'nav-exercise';
          a.href = `#ex-${ex.id}`;
          a.textContent = `${ex.number} ${ex.title}`;
          wrap.appendChild(a);
        }
      }
      nav.appendChild(wrap);
    }
  }

  function renderFilter() {
    const select = document.getElementById('section-filter');
    const sections = [...new Set(window.BOOK_DATA.exercises.map(e => e.section))];
    select.innerHTML = '<option value="all">כל הסעיפים</option>' + sections.map(id => `<option value="${id}">${sectionTitle(id)}</option>`).join('');
    select.addEventListener('change', () => renderExercises(select.value));
  }


  function renderExerciseBody(ex) {
    if (Array.isArray(ex.parts) && ex.parts.length) {
      const partsHtml = ex.parts.map(part => `
        <section class="exercise-part">
          <h4>סעיף ${part.label}${part.title ? ' · ' + part.title : ''}</h4>
          <div class="question-label">שאלה</div>
          <div class="question-body">${part.questionHtml}</div>
          <details class="solution">
            <summary>הצג פתרון סעיף ${part.label}</summary>
            <div class="solution-body">${part.solutionHtml}</div>
          </details>
        </section>
      `).join('');
      return `
        <div class="question-label">מבנה השאלה</div>
        <div class="question-body">${ex.questionHtml || ''}</div>
        <div class="parts-list">${partsHtml}</div>
      `;
    }
    return `
      <div class="question-label">שאלה</div>
      <div class="question-body">${ex.questionHtml}</div>
      <details class="solution">
        <summary>הצג פתרון</summary>
        <div class="solution-body">${ex.solutionHtml}</div>
      </details>
    `;
  }


  function fixBidiFragments(root) {
    // Keep variable tokens with subscripts/superscripts together in one LTR unit.
    root.querySelectorAll('.ltr-inline').forEach(span => {
      span.setAttribute('dir', 'ltr');
      span.style.direction = 'ltr';
      span.style.unicodeBidi = 'isolate-override';
      while (span.nextSibling && span.nextSibling.nodeType === 1 && ['SUB', 'SUP'].includes(span.nextSibling.nodeName)) {
        span.appendChild(span.nextSibling);
      }
    });
  }

  function renderExercises(filterValue = 'all') {
    const list = document.getElementById('exercise-list');
    list.innerHTML = '';
    const exercises = window.BOOK_DATA.exercises.filter(e => filterValue === 'all' || e.section === filterValue);
    let currentSection = null;
    for (const ex of exercises) {
      if (ex.section !== currentSection) {
        currentSection = ex.section;
        const marker = document.createElement('div');
        marker.id = `section-${ex.section.replaceAll('.', '-')}`;
        marker.className = 'section-marker';
        marker.innerHTML = `<h3>${sectionTitle(ex.section)}</h3>`;
        list.appendChild(marker);
      }
      const article = document.createElement('article');
      article.className = 'exercise-card';
      article.id = `ex-${ex.id}`;
      article.innerHTML = `
        <div class="exercise-meta"><span>שאלה ${ex.number}</span><span>·</span><span>${sectionTitle(ex.section)}</span></div>
        <h3 class="exercise-title">${ex.title}</h3>
        ${renderExerciseBody(ex)}
      `;
      list.appendChild(article);
    }
    fixBidiFragments(list);
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.typesetPromise([list]).catch(() => {});
    }
  }

  function setupMenu() {
    const button = document.getElementById('menu-button');
    button.addEventListener('click', () => document.body.classList.toggle('sidebar-open'));
    document.getElementById('book-nav').addEventListener('click', event => {
      if (event.target.closest('a')) document.body.classList.remove('sidebar-open');
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    renderPlan();
    renderNav();
    renderFilter();
    renderExercises();
    setupMenu();
  });
}());
