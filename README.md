# JOB_APP

Installable web app (PWA) for my 2027 internship alerts: **https://purnavasanth01.github.io/JOB_APP/**

```
JOB-LISTENER (GitHub Actions, every 3 min) ──▶ alerts.csv ──▶ this app (phone + Mac)
                                          └──▶ Web Push ──────▶ 🔔 notifications
this app ──▶ sync/state.json (branch "data") ◀── other device   (applied, skipped, ⭐, 🚫 blacklist)
```

| File | What |
|---|---|
| `index.html` | The whole app: tabs, job cards, sync, settings |
| `sw.js` | Service worker: always loads the newest version, shows push notifications |
| `manifest.webmanifest` + icons | Makes "Install app" possible |
| `.nojekyll` | GitHub Pages publishes the files as they are |

## Tabs
`H1B_LIST · Jobright · Workday · Greenhouse · Simplify · HiringCafe · ALL`. Every tab except ALL shows jobs found since 2026-11-11.

## Setup on a new device
1. Open the link in Chrome → ⋮ → **Install app**.
2. ⚙️ → paste the GitHub token ("JOB_APP sync": only this repo, Contents read/write) → **Save token** → status **Synced**.
3. ⚙️ → **🔔 Enable notifications on this device** → Allow.

## Rules for this repo
- `main` = app code only (my own commits). Never edit the `data` branch by hand: the app writes it.
- Commit messages start with a tag: `[FEAT]`, `[FIX]`, `[STYLE]`, `[DOCS]`, `[CHORE]` …
- Bump `VERSION` in `index.html` on every change (shown at the bottom of the app).
