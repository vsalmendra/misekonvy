# Mass texts workflow (decided 2026-10-14, updated 2026-10-20)

## Repo layout (vsalmendra/misekonvy)

The repo is **github.com/vsalmendra/misekonvy** — the single home for this work; it will hold more
content over time. This CLAUDE.md is the source of truth. Claude Code commits and pushes here directly.

- `app/` — the installable web app (PWA): `index.html` (shell + renderer), `manifest.webmanifest`,
  `sw.js`, icons, and the Mass database `app/data/` (generated, committed):
  `calendar.json` (dates that have a Mass) and `masses/<date>.json`.
  **Only this folder is published.** All paths inside it are relative (`./`), so it works from any URL.
  The app takes the day from the device's date only (no URL parameters): today's Mass; the 📅 button
  in the menu offers only dates that have a Mass. No Mass for today → **the Order of Mass alone**
  (`app/data/ordinary.json`: fixed parts, placeholders for the day's prayers, prefaces of EP II and IV,
  all four EPs, Latin section) **with the readings of the liturgical day**: `app/data/days.json` maps
  each date (2026-10 … 2029) to its liturgical day (`tools/litcal.py`) and the key of its readings,
  `app/data/cycle/<key>.json`; any year with the same cycle reuses them,
  plus "Újratöltés" and "Másik nap"; only if nothing can load, the logo.
  **Automatic update (2026-10-29):** the build stamps a hash of `app/` into `index.html`
  (`<meta name="build">`), `version.json` and the SW cache name. At launch and on every resume the page
  fetches `version.json` (no-store; the SW never answers it from cache); if it differs, it clears its
  caches and reloads, keeping the open day and scroll position — only if the reader has not touched the
  page since it opened/came back (else it waits for the next resume), never offline, and at most once per
  server version per 15 min (marker in the tab's sessionStorage; without storage never), so a stale CDN
  copy cannot cause a loop. An installed app resumed on a new day moves on to that day.
- `src/` — sources of the database: `library/` (Order of Mass, Eucharistic prayers, prefaces,
  `commons/`) and `masses/<date>.toml` + `masses/<date>.md` (the day's recipe/instructions).
  `cycle/<key>.json`: lectionary readings by liturgical day (key from `tools/litcal.py`, e.g.
  `evkozi-30-2-II`, `evkozi-31-vas-A`, `advent-1-3`, `fix-11-01`), fetched from igenaptár with
  `python3 tools/fetch_readings.py <from> [<to>]` (igenaptár serves only the current liturgical year;
  overwrites; `--keep` only fills gaps). igenaptár keeps the earlier liturgical years under
  `/2024/` and `/2025/`: all three were fetched (Advent 2023 … Nov 2026) → Sundays A, B, C, weekdays
  I and II. 1089 of 1188 dates up to 2029 covered; the rest are weekdays that were feasts in all
  three years, and the complex days (Palm Sunday, Good Friday, Holy Saturday, 24 Dec, 2 Nov …).
- `tools/build.py` — `python3 tools/build.py` rebuilds `app/data/` and bumps the SW cache name.
  Always run it and commit its output after changing `src/`.
- `tests/app-test.mjs` — browser test (day selection, automatic update: one reload per version, no loops,
  not while reading, not offline; resume on a new day). The publish job runs it first; if it fails, nothing is deployed. Locally:
  `npm i --no-save playwright@1.56.1 && npx playwright install chromium && node tests/app-test.mjs`.
- `docs/ASSEMBLY.md` — **how a Mass is assembled**: file format and the rules learnt so far.
  Read it before adding a day; move recurring patterns from the day recipes into it.

### Adding a day

1. Read `docs/ASSEMBLY.md`. Fetch the day from igenaptár; get propers from the sources listed there.
2. Write `src/masses/<date>.toml` and `src/masses/<date>.md` (the user's instructions, sources, choices, open points).
3. `python3 tools/build.py`, check the page locally (`cd app && python3 -m http.server`), commit, push, merge to `main`.
- `.github/workflows/pages.yml` — deploys `app/` to GitHub Pages on every push to `main` that touches
  `app/` (also runnable by hand). Repo setting required: Settings → Pages → Source = **GitHub Actions**.
  Site URL: https://vsalmendra.github.io/misekonvy/ (the contents of `app/` are the site root).
- Everything else (this file, `README.md`, `src/`, `tools/`, `docs/`) is never published.
- Fonts: loaded from Google Fonts (user decision 2026-10-20: no need to self-host).

## History

- **MOVING TO CLAUDE CODE (2026-10-20):** user wants Claude Code to update GitHub directly. An earlier Python-DSL generator was delivered as a zip; it was **not imported** — superseded by the `src/` + `tools/build.py` database above (2026-10-20). Its contents, for reference:
  - `generator/` (`common.py`, `page.py`, `build_pwa.py`, `build.py` = one command `python3 generator/build.py content/<file>.py` → `docs/`)
  - `content/` (`2026-10-18-evkozi29.py`, `2026-10-20-angyalok.py`)
  - `assets/fonts` (self-hosted woff2 + fontsource CSS + OFL)
  - `scans/`
  - its `CLAUDE.md` (full workflow + rules)
  - `.claude/commands/napi-mise.md` (`/napi-mise <date>`)

- **Output format so far:** mobile web page, ONE FIXED ARTIFACT updated every day: https://claude.ai/artifact/VLf13N3XA4WML4kZ8L9xDr — title "Napi szentmise", shared "Anyone with the link".
  - History: v1–2 Avilai Szent Teréz 10-15 (EP III); v3 Szent Hedvig 10-16 (EP II); v4 Évközi 29. vasárnap 10-18 (dropdowns); v5 Votív mise a szent angyalokról 10-20 (EP I default, all 4 EPs); v6 + Latin–Hungarian section; v7 light/dark toggle; v8 hidden top bar + floating ☰ button; v9 theme toggle moved into toolbar (☾/☀); v10 ↻ refresh button in toolbar.

- **INSTALLABLE APP (PWA):** `build_pwa.py` → `index.html` (manifest, theme-color, SW registration with `updateViaCache:'none'` + update on visibility, slimmer landscape bar), `manifest.webmanifest` (`display=fullscreen`), `sw.js` (network-first, navigations `cache:'no-store'`, offline fallback), icons (white cross on `#a3171b`). GitHub Pages CDN may serve old version ~10 min.
  - **SECURITY (review 2026-10-19, for the zip build):** no third-party JS; fonts self-hosted (now: Google Fonts, by user decision) (Alegreya/Alegreya SC, OFL); CSP `default-src 'self'` (inline script/style allowed), `object-src`/`base-uri`/`form-action` none; referrer `no-referrer`; SW only same-origin GETs, caches only ok/basic responses; localStorage only text size + theme. Verified: zero external requests, ő/ű fonts load, works offline. Advised: GitHub 2FA; copyright of liturgical texts (MKPK) for a public site.

- **Generator DSL:** `h/h2/p/n/v/r/src/sub/c`; `select/opt/end_opt/end_select`; `ep_select(default, saint=None)`; `EP2_PREFACE`, `EP4_PREFACE`; bilingual `bh/bh2/bp/bn/bv/bc/br/bsrc` with ready pairs (`bi_greeting_penitential`, `COLLECT_END`, `bi_gospel_dialogue`, `bi_gifts`, `bi_preface_dialogue`, `bi_sanctus`, `bi_ep1`, `bi_communion_rite`, `bi_concluding`). Content files start with `exec(open(COMMON).read())` (`COMMON` set by `page.py` in the repo version) and end with `# ---------- RENDER`.
  - Menu (floating ☰ bottom-right; since 2026-10-29 a vertical panel just above it, for the thumb): Másik nap, Betűméret A−/A+, Sötét/Világos mód, Frissítés, then "Latin–magyar ›" and "Magyar ›", each opening a jump list of every part of the Mass (bottom sheet; current place marked; switch between the two). Top of page: "Latin–magyar szöveg ↓"; back buttons "↑ Vissza a magyar szöveghez".
  - Latin sources: Missale Romanum 2002 on clerus.org/bibliaclerusonline/en/gl0..gl5.htm; Ordo Missae/EPs/prefaces on ordo.pallotyni.pl; Nova Vulgata on vatican.va (no longer used: only liturgical sources, 2026-10-28). Psalm response/Alleluia Latin not verified against Lectionarium.

- **NEW MISSAL** (Hungarian, from Pentecost 2023; Romania from 29 June 2023). No online copy; 1991 edition on PPEK (EP I/IV taken from it). New-missal changes applied in `common.py`:
  - Confiteor without "Szeplőtelen"
  - "Imádkozzatok, testvéreim, hogy az én áldozatom és a tiétek kedves legyen a mindenható Atyaisten előtt!"
  - "Engesztelődjetek ki szívből egymással!" (people's response dropped — unverified)
  - "Boldogok, akik meghívást kaptak a Bárány lakomájára."
  - preface dialogue with "!"
  - Unverified: St Joseph in EP II–IV.

- **Sunday prefaces I–VIII:** `SUNDAY_PREFACES` in `content-2026-10-18-evkozi29.py`.

- **Sundays:** Gloria + Creed; propers from igenaptar. **Weekdays/memorials/votive:** ferial readings + prayer of the faithful from igenaptar; no Gloria/Creed. **Saints/votive:** scans + common; replace N.; drop "(H. i. alleluja)" outside Eastertime.

- **Pope:** "Leó pápánk(kal/at/ról)", Latin "Papa nostro Leóne"; bishop still N.

- **Strip singing aids:** preface caps/italics/dashes/(Mert)/(és)/(Most)/(zengjük/zengi); psalm asterisks; tone numbers.

- **Sharing via claude.ai:** "Anyone with the link" needs org admin (Organization settings > Artifacts > External sharing); viewers need a Claude account.
