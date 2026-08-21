/* Home: the four-question intake modal drawn on frame 388:1454.
   Question 3 is the one shown in the design; the other three follow its shape. */

import { store } from './store.js';
import { openModal, closeModal } from './app.js';

const QUESTIONS = [
  {
    q: 'What are you hoping this semester looks like?',
    options: ['A steadier week', 'More in my field', 'A lighter load'],
  },
  {
    q: 'How far along are you with your major requirements?',
    options: ['Just starting', 'About halfway', 'Nearly finished'],
  },
  {
    q: 'What are you most focused on this semester?',
    options: ['Applying to internships', 'Raising my GPA', 'Getting involved on campus'],
  },
  {
    q: 'How often should your pigeon check in?',
    options: ['Every morning', 'Once a week', 'Only when something is due'],
  },
];

/* Onboarding state lives in one object under the store's `onboarding` key:
     { seen: true, answers: [...], done: true }
   `seen` is written the moment the intake is first put on screen, so the
   auto-open happens exactly once — on a genuine first visit — no matter how the
   user leaves the modal (× / Escape / backdrop / Done →, or closing the tab
   halfway through). `answers` + `done` are still written separately when the
   user actually finishes, and are never clobbered by the `seen` write. */

function onboarding() {
  return store.all().onboarding ?? {};
}

function patchOnboarding(patch) {
  store.replace({ onboarding: { ...onboarding(), ...patch } });
}

function showIntake() {
  patchOnboarding({ seen: true });
  openModal('intake');
}

const dots    = document.getElementById('intakeDots');
const stepEl  = document.getElementById('intakeStep');
const qEl     = document.getElementById('intakeQ');
const optsEl  = document.getElementById('intakeOptions');
const backBtn = document.getElementById('intakeBack');
const nextBtn = document.getElementById('intakeNext');
const bubble  = document.getElementById('pigeonBubble');

let step = 0;
let answers = onboarding().answers ?? Array(QUESTIONS.length).fill(null);

function render() {
  const item = QUESTIONS[step];

  dots.innerHTML = '';
  QUESTIONS.forEach((_, i) => {
    const d = document.createElement('span');
    d.className = 'intake__dot' + (i <= step ? ' is-on' : '');
    dots.append(d);
  });

  stepEl.textContent = `QUESTION ${step + 1} OF ${QUESTIONS.length}`;
  qEl.textContent = item.q;

  optsEl.innerHTML = '';
  item.options.forEach((label, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'intake__option' + (answers[step] === i ? ' is-on' : '');
    btn.innerHTML = `<span class="intake__radio"></span><span>${label}</span>`;
    btn.addEventListener('click', () => {
      answers[step] = i;
      render();
    });
    optsEl.append(btn);
  });

  backBtn.disabled = step === 0;
  backBtn.style.opacity = step === 0 ? '.4' : '1';
  nextBtn.textContent = step === QUESTIONS.length - 1 ? 'Done →' : 'Next →';
}

backBtn.addEventListener('click', () => {
  if (step > 0) { step -= 1; render(); }
});

nextBtn.addEventListener('click', () => {
  if (step < QUESTIONS.length - 1) {
    step += 1;
    render();
  } else {
    patchOnboarding({ answers, done: true });
    closeModal('intake');
  }
});

bubble.style.pointerEvents = 'auto';
bubble.style.cursor = 'pointer';
bubble.addEventListener('click', () => { step = 0; render(); showIntake(); });

render();

/* Only a genuine first visit gets the intake automatically, the way the frame
   shows it. After that the pigeon's bubble is the way back in. (`done` is
   honoured too, so anyone who finished the intake before this change is not
   asked again.) */
if (!onboarding().seen && !onboarding().done) {
  setTimeout(showIntake, 400);
}
