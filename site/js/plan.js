/* Career Plan board: the whiteboard engine (shared with goals.html), plus the
   board's own behaviour — calendar, habit dots, collage cards, and the
   double-click edit-goal modal from frame 388:1656. */

import { store } from './store.js';
import { openModal, closeModal, init } from './app.js';

/* ===========================================================================
   Whiteboard — pan, zoom, draw, erase, drag a panel, add a panel.

   One transform, one source of truth: `view = { x, y, k }` is written onto
   .wb-stage as `translate(x, y) scale(k)` with transform-origin 0 0. Everything
   in board space (the cards, the SVG ink layer, added panels) is a child of the
   stage, so it all moves together and nothing has to be kept in sync by hand.

       board -> screen :  s = b * k + xy
       screen -> board :  b = (s - xy) / k

   Zoom is anchored to the pointer by solving the second equation for xy with the
   board point held constant, so whatever is under the cursor stays under it.

   Panel drags happen in BOARD units: the screen delta is divided by k before it
   is added to the panel's board position, so the panel tracks the cursor exactly
   at any zoom and stays glued to its neighbours through a later pan or zoom.

   The header, the tools, the zoom pill, the picker and the mascot live outside
   the stage and are `fixed`, which is what keeps them pinned and unscaled.
   =========================================================================== */

const SVG_NS = 'http://www.w3.org/2000/svg';
const MIN_K = 0.4;
const MAX_K = 2.5;
const GRID = 17;               // the dotted paper pitch, scaled with the zoom
const STROKE_W = 2.6;          // board units, so ink scales with the cards

/* A pointerdown on any of these is the element's own business — neither a pan
   nor a panel drag. Checkboxes, buttons, links, fields and contenteditables all
   keep working exactly as they would without the whiteboard. */
const INTERACTIVE = 'a, button, input, textarea, select, label, [contenteditable=""], [contenteditable="true"]';

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function isTyping(el) {
  return !!el && (el.isContentEditable
    || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(el.tagName));
}

function debounce(fn, ms) {
  let t = 0;
  return () => { clearTimeout(t); t = setTimeout(fn, ms); };
}

/* --- panel templates for the + tool ----------------------------------------
   Each one is modelled on a panel the board already has, so the picker adds
   more of the same vocabulary rather than a new one. */

const DOTS = Array.from({ length: 15 }, () =>
  '<button class="habit__dot wb-note__dot" type="button" aria-label="Toggle a day"></button>').join('');

const TEMPLATES = {
  note: {
    label: 'note', width: 236,
    body: '<div class="wb-note__text" contenteditable="true" data-placeholder="type here…"></div>',
  },
  checklist: {
    label: 'checklist', width: 248,
    body:
      '<div class="wb-note__row"><input type="checkbox"><span contenteditable="true" data-placeholder="a step…"></span></div>'
      + '<div class="wb-note__row"><input type="checkbox"><span contenteditable="true" data-placeholder="a step…"></span></div>'
      + '<div class="wb-note__row"><input type="checkbox"><span contenteditable="true" data-placeholder="a step…"></span></div>'
      + '<button class="wb-note__add" type="button" data-add="row">+ add a step</button>',
  },
  habit: {
    label: 'habit tracker', width: 262,
    body:
      '<div class="wb-note__habit"><div contenteditable="true" data-placeholder="habit name…"></div>'
      + `<div class="wb-note__dots">${DOTS}</div></div>`
      + '<p class="wb-note__foot">every tick = a star in the jar</p>',
  },
  people: {
    label: 'person', width: 236,
    body:
      '<div contenteditable="true" data-placeholder="who did you meet?"></div>'
      + '<div class="wb-note__row"><span contenteditable="true" data-placeholder="follow up…"></span></div>'
      + '<p class="wb-note__foot">(pigeon reminds)</p>',
  },
  wins: {
    label: 'wins log', width: 236,
    body:
      '<div class="wb-note__row"><span contenteditable="true" data-placeholder="what went well?"></span></div>'
      + '<button class="wb-note__add" type="button" data-add="win">+ add a win</button>'
      + '<p class="wb-note__foot">turns into resume bullets later</p>',
  },
};

export function initWhiteboard({ canvas, stage, ink, panels, board, tools, zoom, picker, key }) {
  const view = { x: 0, y: 0, k: 1 };
  const strokes = [];            // { w, pts: [[x, y], …], el }
  let notes = [];                // { id, tpl, rot, el }
  let spaceDown = false;
  let seq = 0;
  let zTop = 4;

  const level = zoom?.querySelector('[data-zoom="home"]');
  const addBtn = tools.find((b) => b.dataset.tool === 'add');

  /* --- the transform ------------------------------------------------------ */

  function apply() {
    stage.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.k})`;
    // the paper ground is painted on the viewport, so it has to be panned by hand
    const g = GRID * view.k;
    canvas.style.backgroundSize = `${g}px ${g}px`;
    canvas.style.backgroundPosition = `${view.x}px ${view.y}px`;
    if (level) level.textContent = `${Math.round(view.k * 100)}%`;
  }

  function toBoard(clientX, clientY) {
    const r = canvas.getBoundingClientRect();
    return {
      x: (clientX - r.left - view.x) / view.k,
      y: (clientY - r.top - view.y) / view.k,
    };
  }

  function zoomAt(clientX, clientY, factor) {
    const r = canvas.getBoundingClientRect();
    const b = toBoard(clientX, clientY);          // board point under the cursor
    const k = clamp(view.k * factor, MIN_K, MAX_K);
    if (k === view.k) return;
    view.k = k;
    view.x = (clientX - r.left) - b.x * k;        // …pinned back under the cursor
    view.y = (clientY - r.top) - b.y * k;
    apply();
    saveView();
  }

  function zoomCentre(factor) {
    const r = canvas.getBoundingClientRect();
    zoomAt(r.left + r.width / 2, r.top + r.height / 2, factor);
  }

  /* Home: the whole board width in view, its top edge at the top of the window.
     Board y 0–126 is the band the frame reserved for the header, which is now
     pinned screen chrome sitting over exactly that band. Returns false when the
     canvas has no geometry yet (a background tab, or a hidden ancestor). */
  function home() {
    const r = canvas.getBoundingClientRect();
    const w = board.offsetWidth || 1;
    if (r.width < 1) {
      view.k = 1; view.x = 0; view.y = 0;
      apply();
      return false;
    }
    view.k = clamp(Math.min(1, (r.width - 40) / w), MIN_K, MAX_K);
    view.x = Math.max(0, (r.width - w * view.k) / 2);
    view.y = 0;
    apply();
    saveView();
    return true;
  }

  /* --- persistence -------------------------------------------------------- */

  const saveView = debounce(() => store.set('lists', `${key}-view`, { ...view }), 250);
  const saveInk = debounce(
    () => store.set('lists', `${key}-ink`, strokes.map((s) => ({ w: s.w, pts: s.pts }))), 250);

  /* Board panels persist as a plain id -> {x, y} map, so a panel that has never
     been moved simply has no entry and keeps its CSS (Figma) position. */
  const savePos = debounce(() => {
    const map = {};
    board.querySelectorAll('[data-panel]').forEach((el) => {
      if (el.style.left) map[el.dataset.panel] = { x: parseFloat(el.style.left), y: parseFloat(el.style.top) };
    });
    store.set('lists', `${key}-pos`, Object.keys(map).length ? map : undefined);
  }, 250);

  function syncNote(el) {
    // `checked` is a property, not an attribute — reflect it so innerHTML keeps it
    el.querySelectorAll('input[type="checkbox"]').forEach((i) => {
      if (i.checked) i.setAttribute('checked', ''); else i.removeAttribute('checked');
    });
  }

  const saveNotes = debounce(() => store.set('lists', `${key}-notes`, notes.map((n) => {
    const body = n.el.querySelector('.wb-note__body');
    syncNote(body);
    return {
      id: n.id,
      tpl: n.tpl,
      rot: n.rot,
      x: parseFloat(n.el.style.left) || 0,
      y: parseFloat(n.el.style.top) || 0,
      html: body.innerHTML,
    };
  })), 250);

  /* --- tools -------------------------------------------------------------- */

  const tool = () => tools.find((b) => b.classList.contains('is-on'))?.dataset.tool || '';

  function setTool(name) {
    tools.forEach((b) => b.classList.toggle('is-on', b.dataset.tool === name));
    canvas.dataset.tool = name || '';
  }

  function setPicker(open) {
    if (!picker) return;
    picker.hidden = !open;
    addBtn?.setAttribute('aria-expanded', String(open));
    addBtn?.classList.toggle('is-on', open);
  }

  tools.forEach((btn) => btn.addEventListener('click', () => {
    const t = btn.dataset.tool;
    if (t === 'add') {
      setTool('');
      if (picker) setPicker(picker.hidden);       // the picker is the + tool's UI
      else addPanel('note');
      return;
    }
    setPicker(false);
    setTool(tool() === t ? '' : t);               // exactly one at a time
  }));

  picker?.addEventListener('click', (e) => {
    const opt = e.target.closest('[data-tpl]');
    if (!opt) return;
    addPanel(opt.dataset.tpl);
    setPicker(false);
  });

  /* --- ink ---------------------------------------------------------------- */

  function pathData(pts) {
    if (pts.length === 1) {
      const [x, y] = pts[0];
      return `M${x.toFixed(1)} ${y.toFixed(1)}L${x.toFixed(1)} ${y.toFixed(1)}`;
    }
    return pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join('');
  }

  function addStroke(s) {
    const el = document.createElementNS(SVG_NS, 'path');
    el.setAttribute('class', 'wb-stroke');
    el.setAttribute('stroke-width', String(s.w));
    el.setAttribute('d', pathData(s.pts));
    ink.append(el);
    s.el = el;
    strokes.push(s);
    return s;
  }

  function startStroke(e) {
    const p = toBoard(e.clientX, e.clientY);
    const s = addStroke({ w: STROKE_W, pts: [[p.x, p.y]] });
    drag((ev) => {
      const q = toBoard(ev.clientX, ev.clientY);
      const last = s.pts[s.pts.length - 1];
      if (Math.hypot(q.x - last[0], q.y - last[1]) < 1.2 / view.k) return;
      s.pts.push([q.x, q.y]);
      s.el.setAttribute('d', pathData(s.pts));
    }, saveInk);
  }

  function eraseAt(clientX, clientY) {
    const p = toBoard(clientX, clientY);
    const r = 14 / view.k;
    let hit = false;
    for (let i = strokes.length - 1; i >= 0; i -= 1) {
      const s = strokes[i];
      if (s.pts.some(([x, y]) => Math.hypot(x - p.x, y - p.y) <= r + s.w)) {
        s.el.remove();
        strokes.splice(i, 1);
        hit = true;
      }
    }
    return hit;
  }

  function startErase(e) {
    eraseAt(e.clientX, e.clientY);
    drag((ev) => eraseAt(ev.clientX, ev.clientY), saveInk);
  }

  /* --- added panels ------------------------------------------------------- */

  const ROTS = [-1.6, 1.2, -0.7, 2];

  function makeNote(n) {
    const t = TEMPLATES[n.tpl] || TEMPLATES.note;
    const el = document.createElement('section');
    el.className = `wb-note wb-note--${n.tpl}`;
    el.dataset.panel = n.id;
    el.style.left = `${n.x}px`;
    el.style.top = `${n.y}px`;
    el.style.width = `${t.width}px`;
    el.style.setProperty('--rot', `${n.rot}deg`);
    el.innerHTML = `
      <p class="wb-note__label">
        <span>${t.label}</span>
        <button class="wb-note__del" type="button" aria-label="Delete this panel">×</button>
      </p>
      <div class="wb-note__body">${n.html ?? t.body}</div>`;

    const body = el.querySelector('.wb-note__body');
    // one delegated set of listeners covers every template
    body.addEventListener('input', saveNotes);
    body.addEventListener('change', saveNotes);
    body.addEventListener('click', (e) => {
      const dot = e.target.closest('.wb-note__dot');
      if (dot) { dot.classList.toggle('is-on'); saveNotes(); return; }
      const add = e.target.closest('[data-add]');
      if (!add) return;
      const row = document.createElement('div');
      row.className = 'wb-note__row';
      row.innerHTML = add.dataset.add === 'win'
        ? '<span contenteditable="true" data-placeholder="what went well?"></span>'
        : '<input type="checkbox"><span contenteditable="true" data-placeholder="a step…"></span>';
      add.before(row);
      row.querySelector('[contenteditable]').focus();
      saveNotes();
    });
    el.querySelector('.wb-note__del').addEventListener('click', () => {
      el.remove();
      notes = notes.filter((o) => o !== n);
      saveNotes();
    });

    n.el = el;
    panels.append(el);
    notes.push(n);
    return n;
  }

  /* Drops into the centre of the current view, in board coordinates. */
  function addPanel(tpl = 'note') {
    const r = canvas.getBoundingClientRect();
    const c = toBoard(r.left + r.width / 2, r.top + r.height / 2);
    const t = TEMPLATES[tpl] || TEMPLATES.note;
    seq += 1;
    const n = makeNote({
      id: `n-${Date.now()}-${seq}`,
      tpl: TEMPLATES[tpl] ? tpl : 'note',
      x: Math.round(c.x - t.width / 2 + (seq % 4) * 18),
      y: Math.round(c.y - 80 + (seq % 4) * 18),
      rot: ROTS[seq % ROTS.length],
    });
    saveNotes();
    n.el.querySelector('[contenteditable]')?.focus();
    return n;
  }

  /* --- panel drag (board units) ------------------------------------------- */

  function boardPos(el) {
    // an inline left/top is the moved position; otherwise the CSS (Figma) one,
    // which offsetLeft/Top report directly because every layer origin is (0, 0)
    if (el.style.left) return { x: parseFloat(el.style.left), y: parseFloat(el.style.top) };
    return { x: el.offsetLeft, y: el.offsetTop };
  }

  function startPanelDrag(e, el) {
    const o = boardPos(el);
    const sx = e.clientX;
    const sy = e.clientY;
    let moved = false;
    // No preventDefault: capturing the pointer or eating the default would kill
    // the compatibility click/dblclick that opens the edit-goal modal.
    drag((ev) => {
      const dxs = ev.clientX - sx;
      const dys = ev.clientY - sy;
      if (!moved) {
        if (Math.hypot(dxs, dys) < 3) return;     // a click, not a drag
        moved = true;
        el.classList.add('is-dragging');
        canvas.classList.add('is-dragging');
        el.style.zIndex = String((zTop += 1));
        document.getSelection?.()?.removeAllRanges();
      }
      el.style.left = `${o.x + dxs / view.k}px`;  // <- the /k: board units
      el.style.top = `${o.y + dys / view.k}px`;
    }, () => {
      canvas.classList.remove('is-dragging');
      el.classList.remove('is-dragging');
      if (!moved) return;
      if (el.classList.contains('wb-note')) saveNotes(); else savePos();
    });
  }

  /* --- pan ---------------------------------------------------------------- */

  /* Window-level listeners rather than setPointerCapture: capture retargets the
     compatibility mouse events and would break the double-click that opens the
     edit-goal modal. */
  function drag(onMove, onEnd) {
    const move = (ev) => onMove(ev);
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', up);
      onEnd?.();
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
  }

  function startPan(e) {
    const sx = e.clientX;
    const sy = e.clientY;
    const ox = view.x;
    const oy = view.y;
    let moved = false;
    drag((ev) => {
      const dx = ev.clientX - sx;
      const dy = ev.clientY - sy;
      if (!moved) {
        if (Math.hypot(dx, dy) < 3) return;
        moved = true;
        canvas.classList.add('is-panning');
      }
      view.x = ox + dx;
      view.y = oy + dy;
      apply();
    }, () => {
      canvas.classList.remove('is-panning');
      if (moved) saveView();
    });
  }

  /* --- input -------------------------------------------------------------- */

  canvas.addEventListener('pointerdown', (e) => {
    if (e.button === 2) return;                       // leave the context menu alone
    const t = e.target instanceof Element ? e.target : null;

    // middle-drag and space-drag always pan, even over a card
    if (e.button === 1 || spaceDown) { e.preventDefault(); startPan(e); return; }

    const active = tool();
    if (active === 'draw') { e.preventDefault(); startStroke(e); return; }
    if (active === 'erase') { e.preventDefault(); startErase(e); return; }

    // a checkbox, button, link, field or contenteditable keeps working normally —
    // checked BEFORE the panel drag, so an interactive hit never starts one
    if (t?.closest(INTERACTIVE)) return;

    const panel = t?.closest('[data-panel]');
    if (panel) { startPanelDrag(e, panel); return; }

    startPan(e);
  });

  // Chrome's middle-click autoscroll fires off mousedown, not pointerdown
  canvas.addEventListener('mousedown', (e) => { if (e.button === 1) e.preventDefault(); });

  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();                               // ctrl/cmd+wheel = trackpad pinch
    const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1;
    const dy = clamp(e.deltaY * unit, -320, 320);
    zoomAt(e.clientX, e.clientY, Math.exp(-dy * 0.002));
  }, { passive: false });

  zoom?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-zoom]');
    if (!btn) return;
    if (btn.dataset.zoom === 'in') zoomCentre(1.2);
    else if (btn.dataset.zoom === 'out') zoomCentre(1 / 1.2);
    else home();
  });

  // clicking anywhere off the picker closes it
  window.addEventListener('pointerdown', (e) => {
    if (!picker || picker.hidden) return;
    if (e.target.closest('.wb-picker') || e.target.closest('[data-tool="add"]')) return;
    setPicker(false);
  }, true);

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { setPicker(false); return; }
    if (isTyping(document.activeElement)) return;
    if (e.code === 'Space') { spaceDown = true; canvas.classList.add('is-grab'); e.preventDefault(); return; }
    if (e.key === '0') { home(); return; }
    if (e.key === '1') { zoomCentre(1 / view.k); return; }   // exactly 100%
    if (e.key === '=' || e.key === '+') { zoomCentre(1.2); return; }
    if (e.key === '-' || e.key === '_') zoomCentre(1 / 1.2);
  });
  window.addEventListener('keyup', (e) => {
    if (e.code === 'Space') { spaceDown = false; canvas.classList.remove('is-grab'); }
  });
  window.addEventListener('blur', () => { spaceDown = false; canvas.classList.remove('is-grab'); });

  /* --- restore ------------------------------------------------------------ */

  (store.get('lists', `${key}-ink`, []) || [])
    .forEach((s) => { if (s?.pts?.length) addStroke({ w: s.w || STROKE_W, pts: s.pts }); });

  (store.get('lists', `${key}-notes`, []) || [])
    .forEach((n) => { if (n) makeNote({ ...n, tpl: n.tpl || 'note', rot: n.rot ?? -1 }); });

  const savedPos = store.get('lists', `${key}-pos`, null);
  if (savedPos) {
    Object.entries(savedPos).forEach(([id, p]) => {
      const el = board.querySelector(`[data-panel="${CSS.escape(id)}"]`);
      if (el && Number.isFinite(p?.x)) { el.style.left = `${p.x}px`; el.style.top = `${p.y}px`; }
    });
  }

  const saved = store.get('lists', `${key}-view`, null);
  if (saved && Number.isFinite(saved.k)) {
    view.k = clamp(saved.k, MIN_K, MAX_K);
    view.x = saved.x || 0;
    view.y = saved.y || 0;
    apply();
  } else if (!home()) {
    // No geometry at load (hidden ancestor / zero-sized frame). Retry as soon as
    // the canvas gets a size. rAF and ResizeObserver are not reliable in a hidden
    // document, so plain timers back them up.
    let tries = 0;
    const refit = () => {
      if (home() || (tries += 1) > 40) {
        ro.disconnect();
        clearInterval(timer);
        window.removeEventListener('resize', refit);
        canvas.removeEventListener('pointerdown', refit, true);
      }
    };
    const ro = new ResizeObserver(refit);
    ro.observe(canvas);
    const timer = setInterval(refit, 50);
    window.addEventListener('resize', refit);
    canvas.addEventListener('pointerdown', refit, true);
  }

  return {
    view, strokes, notes, home, zoomAt, zoomCentre, toBoard, addPanel, setTool, tool,
    templates: Object.keys(TEMPLATES),
    limits: { min: MIN_K, max: MAX_K },
  };
}

/* ===========================================================================
   The career-plan board itself. Only runs on plan.html — goals.js imports the
   engine above from this module.
   =========================================================================== */

function bootPlanBoard() {
  /* --- September — 7 day-of-week labels + 35 day cells --------------------- */

  const cal = document.getElementById('calGrid');
  const DOW = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  // Sep 2026 starts on a Tuesday, so the grid opens with Aug 30–31.
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

  /* --- habit dots — 3 habits x 15 dots ------------------------------------ */

  const PRESET = {
    sleep:   [1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1, 0],
    gym:     [0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 0, 1, 1],
    network: [1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1],
  };

  document.querySelectorAll('.habit').forEach((habit) => {
    const key = habit.dataset.habit;
    const host = habit.querySelector('.habit__dots');
    const saved = store.get('lists', `habit-${key}`, PRESET[key]);
    saved.forEach((on, i) => {
      const dot = document.createElement('button');
      dot.className = 'habit__dot' + (on ? ' is-on' : '');
      dot.type = 'button';
      dot.setAttribute('aria-label', `Day ${i + 1}`);
      dot.addEventListener('click', () => {
        dot.classList.toggle('is-on');
        const next = [...host.children].map((d) => (d.classList.contains('is-on') ? 1 : 0));
        store.set('lists', `habit-${key}`, next);
      });
      host.append(dot);
    });
  });

  /* --- edit-goal modal ---------------------------------------------------- */

  const goalList = document.getElementById('goalList');
  const geName   = document.getElementById('geName');
  const geDue    = document.getElementById('geDue');
  const gePri    = document.getElementById('gePriority');
  let editing = null;

  function paintPriority(pri) {
    gePri.querySelectorAll('.pri').forEach((b) => b.classList.toggle('is-on', b.dataset.pri === pri));
  }

  function openGoal(article) {
    editing = article;
    geName.textContent = article.querySelector('.pl-goal__name').textContent;
    geDue.value = article.dataset.due || '';
    paintPriority(article.dataset.pri || 'medium');
    openModal('goalEdit');
  }

  goalList.addEventListener('dblclick', (e) => {
    const article = e.target.closest('.pl-goal');
    if (article) openGoal(article);
  });

  gePri.addEventListener('click', (e) => {
    const btn = e.target.closest('.pri');
    if (btn) paintPriority(btn.dataset.pri);
  });

  document.getElementById('geSave').addEventListener('click', () => {
    if (editing) {
      editing.dataset.due = geDue.value;
      // the badge colour is driven off data-pri, so this repaints it too
      editing.dataset.pri = gePri.querySelector('.pri.is-on')?.dataset.pri || 'medium';
    }
    closeModal('goalEdit');
  });

  document.getElementById('geDelete').addEventListener('click', () => {
    editing?.remove();
    editing = null;
    closeModal('goalEdit');
    refreshCount();
  });

  /* --- add a goal --------------------------------------------------------- */

  let goalSeq = 0;

  function refreshCount() {
    const n = goalList.querySelectorAll('.pl-goal').length;
    document.getElementById('goalCount').textContent = `${n} goal${n === 1 ? '' : 's'}`;
  }

  document.getElementById('addGoal').addEventListener('click', () => {
    const name = prompt('Goal');
    if (!name) return;
    goalSeq += 1;
    const rank = goalList.querySelectorAll('.pl-goal__badge').length + 1;
    const article = document.createElement('article');
    article.className = 'pl-goal';
    article.dataset.goal = `new-${goalSeq}`;
    article.dataset.pri = 'medium';
    article.dataset.due = '';
    article.innerHTML = `
      <span class="pl-goal__badge">${rank}</span>
      <div class="pl-goal__row">
        <input class="pl-check" type="checkbox" data-check="pl-goal-new-${goalSeq}">
        <span class="pl-goal__name"></span>
      </div>
      <div class="pl-goal__meta"><p>where? · how?</p></div>`;
    article.querySelector('.pl-goal__name').textContent = name;
    goalList.append(article);
    init(article);
    refreshCount();
  });

  refreshCount();

  /* --- the smaller collage affordances ------------------------------------ */

  document.getElementById('addTask').addEventListener('click', () => {
    const text = prompt('Task for today');
    if (!text) return;
    const label = document.createElement('label');
    label.className = 'pl-week__task';
    label.innerHTML = '<input type="checkbox"><span></span>';
    label.querySelector('span').textContent = text;
    document.getElementById('weekTasks').append(label);
  });

  document.getElementById('addInterest').addEventListener('click', () => {
    const text = prompt('Goal or interest');
    if (!text) return;
    const chip = document.createElement('span');
    chip.className = 'pl-long__chip';
    chip.textContent = text;
    document.getElementById('interestChips').append(chip);
  });

  document.getElementById('addPerson').addEventListener('click', () => {
    const text = prompt('Who did you meet?');
    if (!text) return;
    const p = document.createElement('p');
    p.className = 'pl-people__name';
    p.textContent = text;
    document.getElementById('peopleList').append(p);
  });

  document.getElementById('addWin').addEventListener('click', () => {
    const text = prompt('What went well?');
    if (!text) return;
    const p = document.createElement('p');
    p.className = 'pl-wins__item';
    p.textContent = text;
    document.getElementById('winsList').append(p);
  });

  const share = document.getElementById('shareToggle');
  share.classList.toggle('is-on', store.get('checks', 'plan-share', false));
  share.setAttribute('aria-pressed', String(share.classList.contains('is-on')));
  share.addEventListener('click', () => {
    const on = store.toggle('checks', 'plan-share');
    share.classList.toggle('is-on', on);
    share.setAttribute('aria-pressed', String(on));
  });

  /* --- the board becomes a whiteboard ------------------------------------- */

  window.whiteboard = initWhiteboard({
    canvas: document.getElementById('wbCanvas'),
    stage:  document.getElementById('wbStage'),
    ink:    document.getElementById('wbInk'),
    panels: document.getElementById('wbPanels'),
    board:  document.getElementById('board'),
    zoom:   document.getElementById('wbZoom'),
    picker: document.getElementById('wbPicker'),
    tools:  [...document.querySelectorAll('.pl-tools button')],
    key:    'plan',
  });
}

if (document.body.classList.contains('page-plan')) bootPlanBoard();
