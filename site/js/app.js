/* Shared behaviour every screen gets:
     [data-bookmark="id"]   toggle + persist a bookmark button
     [data-check="id"]      toggle + persist a checkbox
     [data-field="id"]      persist an input/textarea value
     [data-dismiss="id"]    hide a banner for good
     [data-modal="id"]      open the modal with that id
     [data-modal-close]     close the nearest modal
   Page-specific logic lives in its own module and imports from here. */

import { store } from './store.js';

/* --- bookmarks ------------------------------------------------------------- */

function paintBookmark(el, on) {
  el.classList.toggle('is-on', on);
  el.setAttribute('aria-pressed', String(on));
}

function initBookmarks(root) {
  root.querySelectorAll('[data-bookmark]').forEach((el) => {
    const id = el.dataset.bookmark;
    paintBookmark(el, store.get('bookmarks', id, false));
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      paintBookmark(el, store.toggle('bookmarks', id));
    });
  });
}

/* --- checkboxes ------------------------------------------------------------ */

function initChecks(root) {
  root.querySelectorAll('[data-check]').forEach((el) => {
    const id = el.dataset.check;
    el.checked = store.get('checks', id, false);
    el.closest('[data-check-row]')?.classList.toggle('is-done', el.checked);
    el.addEventListener('change', () => {
      store.set('checks', id, el.checked || undefined);
      el.closest('[data-check-row]')?.classList.toggle('is-done', el.checked);
    });
  });
}

/* --- text fields ----------------------------------------------------------- */

function initFields(root) {
  root.querySelectorAll('[data-field]').forEach((el) => {
    const id = el.dataset.field;
    const saved = store.get('fields', id);
    if (saved !== undefined) el.value = saved;
    el.addEventListener('input', () => {
      store.set('fields', id, el.value || undefined);
      autosize(el);
    });
    autosize(el);
  });
}

function autosize(el) {
  if (el.tagName !== 'TEXTAREA' || !el.hasAttribute('data-autosize')) return;
  el.style.height = 'auto';
  el.style.height = `${el.scrollHeight}px`;
}

/* --- dismissible banners --------------------------------------------------- */

function initDismiss(root) {
  root.querySelectorAll('[data-dismiss]').forEach((el) => {
    const id = el.dataset.dismiss;
    const target = el.closest('[data-dismiss-target]') || el.parentElement;
    if (store.get('dismissed', id, false)) target.hidden = true;
    el.addEventListener('click', () => {
      store.set('dismissed', id, true);
      target.hidden = true;
    });
  });
}

/* --- modals ---------------------------------------------------------------- */

let lastFocus = null;

export function openModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  lastFocus = document.activeElement;
  el.classList.add('is-open');
  document.body.style.overflow = 'hidden';
  (el.querySelector('[autofocus]') || el.querySelector('button, input, textarea, a'))?.focus();
}

export function closeModal(el) {
  const target = typeof el === 'string' ? document.getElementById(el) : el;
  if (!target) return;
  target.classList.remove('is-open');
  if (!document.querySelector('.modal-backdrop.is-open')) document.body.style.overflow = '';
  lastFocus?.focus();
}

function initModals(root) {
  root.querySelectorAll('[data-modal]').forEach((el) => {
    el.addEventListener('click', () => openModal(el.dataset.modal));
  });
  root.querySelectorAll('.modal-backdrop').forEach((back) => {
    back.addEventListener('mousedown', (e) => {
      if (e.target === back) closeModal(back);
    });
    back.querySelectorAll('[data-modal-close]').forEach((btn) => {
      btn.addEventListener('click', () => closeModal(back));
    });
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') document.querySelectorAll('.modal-backdrop.is-open').forEach(closeModal);
  });
}

/* --- boot ------------------------------------------------------------------ */

export function init(root = document) {
  initBookmarks(root);
  initChecks(root);
  initFields(root);
  initDismiss(root);
  initModals(root);
}

document.addEventListener('DOMContentLoaded', () => init());
