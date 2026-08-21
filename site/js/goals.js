/* Goals board — Figma 388:571. Shares the September calendar with the plan board,
   and the whiteboard engine (pan / zoom / draw / erase / add a panel) with it too:
   initWhiteboard lives in plan.js, which only boots its own page when it is on it. */

import { store } from './store.js';
import { initWhiteboard } from './plan.js';

const cal = document.getElementById('calGrid');
const DOW = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const CELLS = [
  { n: 30, mute: true }, { n: 31, mute: true }, { n: 1 }, { n: 2 }, { n: 3 }, { n: 4 }, { n: 5 },
  { n: 6 }, { n: 7 }, { n: 8, today: true }, { n: 9 }, { n: 10 }, { n: 11 }, { n: 12 },
  ...Array.from({ length: 19 }, () => ({ n: '' })),
  { n: '', dark: true }, { n: '', dark: true },
];

DOW.forEach((d) => {
  const el = document.createElement('div');
  el.className = 'cal__dow';
  el.textContent = d;
  cal.append(el);
});

CELLS.forEach((c) => {
  const el = document.createElement('div');
  el.className = 'cal__day'
    + (c.mute ? ' cal__day--mute' : '')
    + (c.dark ? ' cal__day--dark' : '')
    + (c.today ? ' cal__day--today' : '');
  el.textContent = c.n;
  cal.append(el);
});

/* --- editable goal cards --------------------------------------------------- */

document.querySelectorAll('.gcard__title[contenteditable]').forEach((el, i) => {
  const id = `g-title-${i}`;
  el.textContent = store.get('fields', id, '');
  el.addEventListener('input', () => store.set('fields', id, el.textContent.trim() || undefined));
});

document.querySelectorAll('.gcard__add').forEach((btn) => {
  btn.addEventListener('click', () => {
    const text = prompt('Step');
    if (!text) return;
    const card = btn.closest('.gcard');
    let list = card.querySelector('.gcard__list');
    if (!list) {
      list = document.createElement('ul');
      list.className = 'gcard__list';
      card.append(list);
    }
    const li = document.createElement('li');
    li.textContent = text;
    li.addEventListener('click', () => li.classList.toggle('is-done'));
    list.append(li);
  });
});

document.querySelectorAll('.gcard__list li').forEach((li) => {
  li.addEventListener('click', () => li.classList.toggle('is-done'));
});

/* --- the board becomes a whiteboard ---------------------------------------- */

window.whiteboard = initWhiteboard({
  canvas: document.getElementById('wbCanvas'),
  stage:  document.getElementById('wbStage'),
  ink:    document.getElementById('wbInk'),
  panels: document.getElementById('wbPanels'),
  board:  document.getElementById('board'),
  zoom:   document.getElementById('wbZoom'),
  tools:  [...document.querySelectorAll('.gb-tools button')],
  key:    'goals',
});
