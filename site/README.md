# Stellic Pathfinders — site

Static build of **Page 4** of the Figma file
[Stellic FrontEnd Design](https://www.figma.com/design/Bg342a4k8osKHaxsL09w5q/Stellic-FrontEnd-Design?node-id=388-55).
Plain HTML, CSS and ES modules — no build step and no dependencies.

## Run

```bash
python -m http.server 5173 --directory site
```

Then open <http://localhost:5173>. (There is also a `site` entry in `.claude/launch.json`.)

## Pages

| File | Figma frame | Notes |
| --- | --- | --- |
| `index.html` | `388:1275` Desktop - 14, `388:1454` Desktop - 15 | Home dashboard; the four-question intake modal opens on first visit and from the pigeon's speech bubble. |
| `career.html` | `388:56`, `388:245`, `388:470` Desktop - 9 (Career) | All three states of one screen: compact grid, expanded grid (the ⤢ toggle), and the start-up detail pane. |
| `plan.html` | `388:669`, `388:1656` Personalized Career Plan | The collage board. Double-click a goal to open the edit-goal modal. |
| `goals.html` | `388:571` Desktop - 9 (Goals) | Goals / Brain Dump / Habits board. |
| `profile.html` | `388:964` Desktop - 10 (Profile) | Identity, advisors, saved listings, experiences, week schedule. |
| `resume.html` | `388:1145` Desktop - 12 (Resume Editor) | Editor and Preview modes; Export PDF prints the preview. |
| `planner.html` | — | Hosts the Compass Planner bundle in a full-bleed iframe, so the bundle's own CSS/JS stays isolated. A New/Old toggle picks between `planner-new-app.html` and `planner-app.html` (a byte-for-byte copy of the repo-root `Compass Planner.html`). The new copy is the same app with two board changes: prerequisite routes are drawn only for the selected course's strand, and each semester block packs its courses on one grid. |
| `contacts.html` | — | The advisor cards from `388:964`, on their own page. Built from the existing `.advisor` / `.advisor-add` components in `css/profile.css`. |

Nothing in the Figma file was modified.

## Layout

```
site/
  *.html          one file per screen
  css/
    base.css      design tokens, app shell, sidebar, shared primitives
    schedule.css  the week grid, shared by Home and Profile
    career.css  home.css  profile.css  resume.css  plan.css  goals.css
    planner.css  duck.css
  js/
    store.js      localStorage-backed state, one JSON blob under `stellic-pathfinders`
    app.js        shared behaviour: bookmarks, checkboxes, text fields, banners, modals
    career.js  home.js  profile.js  resume.js  plan.js  goals.js
  assets/         PNGs and SVGs exported from the Figma frames
```

Anything marked `data-bookmark`, `data-check` or `data-field` persists to
localStorage automatically and is shared across screens — the goals ticked on Home
are the same records the Career Plan board edits.

## Two deliberate departures from the file

- **Sidebar.** Each frame was drawn with a different sidebar (`Oliver Gan` /
  `Name of Site` / `Study Maxing`, and 140/165/170/217px widths, with different nav
  items). Every page now uses one canonical sidebar instead, taken from the most
  complete frame — Home `388:1275`: 217px wide, `Name of Site`, and five nav items
  (Home / Planner / Goals / Career / Contacts). It lives entirely in `css/base.css`;
  no page overrides it. The footer avatar is the link to `profile.html`.
- **Headline font.** The frames use `Pathfinder Hand`, which is not a
  distributable webfont. `--font-hand` is a stack — `'Pathfinder Hand', 'Patrick
  Hand', 'Caveat', cursive` — so the real face is used wherever it is installed and
  a close hand-drawn substitute is used otherwise. Body text (Inter), card titles
  (Playfair Display), nav (Caveat) and the board cards (Playpen Sans) are the fonts
  the file specifies, loaded from Google Fonts.
