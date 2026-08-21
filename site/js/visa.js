/* International Student Visa — Figma 421:276.

   Everything that persists goes through the shared helpers in app.js:
   the seven roadmap lessons and the five quick-question chips are all
   [data-check] inputs, so app.js restores and stores them. This module only
   adds the derived bits the frame draws as static text:

     · the "N of 7 done" line and the roadmap progress bar
     · the "Continue: …" link, which points at the first unfinished lesson
     · the OIE mail link, built from whichever question chips are lit
     · "Show me how", which jumps to the gap-semester lesson

   NOTE ON ORDER: this module's body runs before app.js's DOMContentLoaded
   handler (both are deferred modules, and app.js registers its listener when
   its body runs). That is deliberate — the default two ticked lessons are
   seeded into the store here, so initChecks picks them up. */

import { store } from './store.js';

/* --- one-time seed: the frame ships with the first two lessons done -------- */

if (!store.get('fields', 'visa-seeded')) {
  store.set('checks', 'visa-lesson-1', true);
  store.set('checks', 'visa-lesson-2', true);
  store.set('fields', 'visa-seeded', '1');
}

/* --- derived UI ------------------------------------------------------------ */

const OIE = 'oie@andrew.cmu.edu';

const lessons  = [...document.querySelectorAll('#lessons .vs-check')];
const lede     = document.getElementById('roadmapLede');
const bar      = document.getElementById('roadmapBar');
const cont     = document.getElementById('roadmapContinue');
const chips    = [...document.querySelectorAll('#quickQuestions input[data-check]')];
const send     = document.getElementById('sendQuestion');
const timeOff  = document.getElementById('lessonTimeOff');
const howBtn   = document.getElementById('showMeHow');

function titleOf(input) {
  return input.closest('.vs-lesson').querySelector('.vs-lesson__title').textContent;
}

function paintRoadmap() {
  const done = lessons.filter((el) => el.checked).length;
  lede.textContent = `10-minute lessons, in plain language. ${done} of ${lessons.length} done.`;
  bar.style.width = `${(done / lessons.length) * 100}%`;

  const next = lessons.find((el) => !el.checked);
  cont.textContent = next
    ? `Continue: ${titleOf(next)} →`
    : 'Every lesson done — Pigeon is impressed →';
}

function paintQuestion() {
  const picked = chips
    .filter((el) => el.checked)
    .map((el) => el.closest('.vs-chip').textContent.trim());
  const subject = picked.length ? picked.join(', ') : 'Question about my F-1 status';
  send.href = `mailto:${OIE}?subject=${encodeURIComponent(subject)}`;
}

/* app.js restores the stored values on DOMContentLoaded; this listener is
   registered later, so it runs after that and sees the restored state. */
document.addEventListener('DOMContentLoaded', () => {
  paintRoadmap();
  paintQuestion();
});

lessons.forEach((el) => el.addEventListener('change', paintRoadmap));
chips.forEach((el) => el.addEventListener('change', paintQuestion));

/* --- "Show me how" points at the lesson that answers it -------------------- */

howBtn?.addEventListener('click', () => {
  timeOff.scrollIntoView({ block: 'center', behavior: 'smooth' });
  timeOff.classList.add('is-flagged');
  setTimeout(() => timeOff.classList.remove('is-flagged'), 2200);
});

cont?.addEventListener('click', () => {
  const next = lessons.find((el) => !el.checked);
  next?.closest('.vs-lesson').scrollIntoView({ block: 'center', behavior: 'smooth' });
});
