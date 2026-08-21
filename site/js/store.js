/* Tiny localStorage-backed store shared by every screen.
   One JSON blob under a single key so a page can read another page's state
   (e.g. Home reads the goals the Career Plan board owns). */

const KEY = 'stellic-pathfinders';

const DEFAULTS = {
  bookmarks: {},        // id -> true
  checks: {},           // id -> true
  fields: {},           // id -> string
  lists: {},            // id -> array
  onboarding: null,     // answers from the Home intake modal
  dismissed: {},        // banner id -> true
};

function read() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
  } catch {
    return { ...DEFAULTS };
  }
}

function write(state) {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* private mode / quota — the UI still works, it just won't persist */
  }
}

export const store = {
  all: read,

  get(bucket, id, fallback = undefined) {
    const b = read()[bucket];
    return b && id in b ? b[id] : fallback;
  },

  set(bucket, id, value) {
    const state = read();
    state[bucket] = state[bucket] || {};
    if (value === undefined || value === null || value === false) {
      delete state[bucket][id];
    } else {
      state[bucket][id] = value;
    }
    write(state);
  },

  toggle(bucket, id) {
    const next = !store.get(bucket, id, false);
    store.set(bucket, id, next || undefined);
    return next;
  },

  replace(patch) {
    write({ ...read(), ...patch });
  },
};
