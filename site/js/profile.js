/* Profile: the three "+ Add …" affordances drawn on frame 388:964. */

import { store } from './store.js';

/* --- skills ---------------------------------------------------------------- */

const skills = document.getElementById('skills');

function addSkillChip(text) {
  const chip = document.createElement('span');
  chip.className = 'skill';
  chip.textContent = text;
  skills.append(chip);
}

store.get('lists', 'skills', []).forEach(addSkillChip);

document.getElementById('addSkill').addEventListener('click', () => {
  const text = prompt('Skill');
  if (!text) return;
  addSkillChip(text);
  store.set('lists', 'skills', [...store.get('lists', 'skills', []), text]);
});

/* --- experiences ----------------------------------------------------------- */

const expList = document.getElementById('expList');

function addExpItem({ role, meta }) {
  const el = document.createElement('div');
  el.className = 'pf-exp__item';
  el.innerHTML = `<h3 class="pf-exp__role"></h3><p class="pf-exp__meta"></p>`;
  el.querySelector('.pf-exp__role').textContent = role;
  el.querySelector('.pf-exp__meta').textContent = meta;
  expList.append(el);
}

store.get('lists', 'experiences', []).forEach(addExpItem);

document.getElementById('addExperience').addEventListener('click', () => {
  const role = prompt('Role or title');
  if (!role) return;
  const meta = prompt('Organisation · start date') || '';
  addExpItem({ role, meta });
  store.set('lists', 'experiences', [...store.get('lists', 'experiences', []), { role, meta }]);
});

/* --- extra contact card ---------------------------------------------------- */

document.getElementById('addContact').addEventListener('click', () => {
  const name = prompt('Contact name');
  if (!name) return;
  const card = document.createElement('article');
  card.className = 'advisor';
  card.innerHTML = `
    <div class="advisor__left">
      <p class="eyebrow" style="font-size:12px;letter-spacing:.96px">Contact</p>
      <div class="advisor__avatar"></div>
      <h3 class="advisor__name"></h3>
    </div>
    <div class="advisor__fields">
      <p class="advisor__label">EMAIL</p>
      <p class="advisor__value">—</p>
      <p class="advisor__label">PHONE</p>
      <p class="advisor__value">—</p>
    </div>`;
  card.querySelector('.advisor__name').textContent = name;
  document.querySelector('.pf-row2').append(card);
});
