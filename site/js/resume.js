/* Resume editor: collapse, entries, skill chips, editor/preview, export.
   Field values persist through the shared [data-field] wiring in app.js. */

import { store } from './store.js';
import { init } from './app.js';

const page = document.body;

/* --- collapse -------------------------------------------------------------- */

document.querySelectorAll('[data-collapse]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const card = btn.closest('[data-card]');
    const on = card.classList.toggle('is-collapsed');
    btn.textContent = on ? '›' : '⌄';
    btn.setAttribute('aria-label', on ? 'Expand section' : 'Collapse section');
  });
});

/* --- entries --------------------------------------------------------------- */

let entrySeq = 0;

const TEMPLATES = {
  experience: () => `
    <div class="rz-entry">
      <span class="rz-entry__grip">⋮⋮</span>
      <button class="rz-entry__remove" data-remove aria-label="Remove entry">×</button>
      <div class="rz-fields">
        <input class="rz-input" data-field="rz-exp-n${entrySeq}-title"   placeholder="Job title">
        <input class="rz-input" data-field="rz-exp-n${entrySeq}-company" placeholder="Company name">
        <input class="rz-input" data-field="rz-exp-n${entrySeq}-place"   placeholder="City, State">
        <input class="rz-input" data-field="rz-exp-n${entrySeq}-dates"   placeholder="Start – End">
        <textarea class="rz-textarea rz-span2" data-field="rz-exp-n${entrySeq}-bullets" placeholder="• Describe your impact — start with an action verb..."></textarea>
      </div>
    </div>`,
  education: () => `
    <div class="rz-entry">
      <span class="rz-entry__grip">⋮⋮</span>
      <button class="rz-entry__remove" data-remove aria-label="Remove entry">×</button>
      <div class="rz-fields">
        <input class="rz-input rz-span2" data-field="rz-edu-n${entrySeq}-school" placeholder="University name">
        <input class="rz-input" data-field="rz-edu-n${entrySeq}-degree" placeholder="Degree">
        <input class="rz-input" data-field="rz-edu-n${entrySeq}-dates"  placeholder="Expected">
        <input class="rz-input rz-span2" data-field="rz-edu-n${entrySeq}-notes" placeholder="Honours, GPA, activities">
      </div>
    </div>`,
  certs: () => `
    <div class="cert-row">
      <span class="cert-row__grip">⋮⋮</span>
      <input class="rz-input" data-field="rz-cert-n${entrySeq}-name" placeholder="Certification name">
      <input class="rz-input" data-field="rz-cert-n${entrySeq}-date" placeholder="Date">
    </div>`,
};

document.querySelectorAll('[data-add-entry]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const kind = btn.dataset.addEntry;
    const host = document.querySelector(`[data-entries="${kind}"]`);
    entrySeq += 1;
    host.insertAdjacentHTML('beforeend', TEMPLATES[kind]());
    init(host.lastElementChild);
    wireRemove(host.lastElementChild);
  });
});

function wireRemove(scope) {
  scope.querySelectorAll?.('[data-remove]').forEach((btn) => {
    btn.addEventListener('click', () => {
      btn.closest('.rz-entry').querySelectorAll('[data-field]').forEach((f) => store.set('fields', f.dataset.field, undefined));
      btn.closest('.rz-entry').remove();
    });
  });
  if (scope.matches?.('[data-remove]')) return;
}

document.querySelectorAll('.rz-entry').forEach(wireRemove);

/* --- add category ---------------------------------------------------------- */

document.querySelectorAll('[data-add-category]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const name = prompt('Category name');
    if (!name) return;
    entrySeq += 1;
    const id = `rz-cat-${entrySeq}`;
    const card = document.createElement('section');
    card.className = 'rz-card';
    card.dataset.card = '';
    card.innerHTML = `
      <div class="rz-card__head">
        <span class="rz-grip">⋮⋮</span>
        <h2 class="rz-card__title"></h2>
        <span class="rz-card__badge">TEXT</span>
        <button class="rz-card__menu" aria-label="Section options">⋮</button>
        <button class="rz-card__collapse" data-collapse aria-label="Collapse section">⌄</button>
      </div>
      <hr class="divider">
      <div class="rz-card__body">
        <textarea class="rz-textarea rz-textarea--tall" data-field="${id}" placeholder="Add the details for this section..."></textarea>
      </div>`;
    card.querySelector('.rz-card__title').textContent = name;
    btn.parentElement.insertBefore(card, btn);
    init(card);
    card.querySelector('[data-collapse]').addEventListener('click', () => {
      card.classList.toggle('is-collapsed');
    });
  });
});

/* --- skill chips ----------------------------------------------------------- */

const chipsHost = document.getElementById('rzChips');
const DEFAULT_SKILLS = ['Python', 'React', 'SQL', 'Figma', 'Git', 'Communication'];

function skills() {
  return store.get('lists', 'rz-skills', DEFAULT_SKILLS);
}

function renderChips() {
  chipsHost.innerHTML = '';
  skills().forEach((name, i) => {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.innerHTML = '<span></span><button aria-label="Remove skill">×</button>';
    chip.firstElementChild.textContent = name;
    chip.lastElementChild.addEventListener('click', () => {
      const next = skills().filter((_, j) => j !== i);
      store.set('lists', 'rz-skills', next);
      renderChips();
    });
    chipsHost.append(chip);
  });
}

document.getElementById('rzAddSkill').addEventListener('click', () => {
  const name = prompt('Skill');
  if (!name) return;
  store.set('lists', 'rz-skills', [...skills(), name]);
  renderChips();
});

renderChips();

/* --- editor / preview ------------------------------------------------------ */

const paper = document.getElementById('rzPaper');

function val(id) {
  return (document.querySelector(`[data-field="${id}"]`)?.value || '').trim();
}

function bullets(text) {
  const items = text.split('\n').map((l) => l.replace(/^[•\-\s]+/, '').trim()).filter(Boolean);
  return items.length ? `<ul>${items.map((i) => `<li>${escape(i)}</li>`).join('')}</ul>` : '';
}

function escape(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderPreview() {
  const parts = [`<h1>Jordan Lee</h1>`];

  const summary = val('rz-summary');
  if (summary) parts.push(`<h2>Summary</h2><p>${escape(summary)}</p>`);

  const exps = [...document.querySelectorAll('[data-entries="experience"] .rz-entry')]
    .map((e) => [...e.querySelectorAll('[data-field]')].map((f) => f.value.trim()))
    .filter((v) => v.some(Boolean));
  if (exps.length) {
    parts.push('<h2>Experience</h2>');
    exps.forEach(([title, company, place, dates, body]) => {
      parts.push(`<p class="rz-paper__role">${escape(title)}${company ? ` · ${escape(company)}` : ''}</p>`);
      if (place || dates) parts.push(`<p>${escape([place, dates].filter(Boolean).join(' · '))}</p>`);
      if (body) parts.push(bullets(body));
      parts.push('<div style="height:14px"></div>');
    });
  }

  const edus = [...document.querySelectorAll('[data-entries="education"] .rz-entry')]
    .map((e) => [...e.querySelectorAll('[data-field]')].map((f) => f.value.trim()))
    .filter((v) => v.some(Boolean));
  if (edus.length) {
    parts.push('<h2>Education</h2>');
    edus.forEach(([school, degree, dates, notes]) => {
      parts.push(`<p class="rz-paper__role">${escape(school)}</p>`);
      parts.push(`<p>${escape([degree, dates].filter(Boolean).join(' · '))}</p>`);
      if (notes) parts.push(`<p>${escape(notes)}</p>`);
      parts.push('<div style="height:14px"></div>');
    });
  }

  if (skills().length) {
    parts.push('<h2>Skills</h2>');
    parts.push(`<p>${skills().map(escape).join(' · ')}</p>`);
  }

  const certs = [...document.querySelectorAll('[data-entries="certs"] .cert-row')]
    .map((r) => [...r.querySelectorAll('[data-field]')].map((f) => f.value.trim()))
    .filter((v) => v.some(Boolean));
  if (certs.length) {
    parts.push('<h2>Certifications</h2>');
    certs.forEach(([name, date]) => parts.push(`<p>${escape(name)}${date ? ` — ${escape(date)}` : ''}</p>`));
  }

  paper.innerHTML = parts.join('');
}

document.getElementById('rzMode').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-mode]');
  if (!btn) return;
  const preview = btn.dataset.mode === 'preview';
  document.querySelectorAll('#rzMode button').forEach((b) => {
    b.classList.toggle('is-on', b === btn);
    b.setAttribute('aria-selected', String(b === btn));
  });
  page.classList.toggle('is-preview', preview);
  if (preview) renderPreview();
});

document.getElementById('rzExport').addEventListener('click', () => {
  page.classList.add('is-preview');
  document.querySelectorAll('#rzMode button').forEach((b) => {
    const on = b.dataset.mode === 'preview';
    b.classList.toggle('is-on', on);
    b.setAttribute('aria-selected', String(on));
  });
  renderPreview();
  window.print();
});
