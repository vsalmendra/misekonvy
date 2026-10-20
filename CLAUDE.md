# Mass texts workflow (decided 2026-10-14, updated 2026-10-20)

## Repo layout (vsalmendra/misekonvy)

The repo is **github.com/vsalmendra/misekonvy** — the single home for this work; it will hold more
content over time. This CLAUDE.md is the source of truth. Claude Code commits and pushes here directly.

- `app/` — the installable web app (PWA): `index.html`, `manifest.webmanifest`, `sw.js`, icons.
  **Only this folder is published.** All paths inside it are relative (`./`), so it works from any URL.
- `.github/workflows/pages.yml` — deploys `app/` to GitHub Pages on every push to `main` that touches
  `app/` (also runnable by hand). Repo setting required: Settings → Pages → Source = **GitHub Actions**.
  Site URL: https://vsalmendra.github.io/misekonvy/ (the contents of `app/` are the site root).
- Everything else at top level (this file, `README.md`, future `generator/`, `content/`, `assets/`,
  `scans/`) is never published.

- **MOVING TO CLAUDE CODE (2026-10-20):** user wants Claude Code to update GitHub directly. The generator and sources were delivered as a zip (branch `main`, 1 commit) and are still to be imported into this repo:
  - `generator/` (`common.py`, `page.py`, `build_pwa.py`, `build.py` = one command `python3 generator/build.py content/<file>.py` → `app/`; the zip version wrote to `docs/`, change its output dir to `app/` when importing)
  - `content/` (`2026-10-18-evkozi29.py`, `2026-10-20-angyalok.py`)
  - `assets/fonts` (self-hosted woff2 + fontsource CSS + OFL); the font files the page loads must be copied into `app/`
  - `scans/`
  - its `CLAUDE.md` (full workflow + rules) — merge into this file
  - `.claude/commands/napi-mise.md` (`/napi-mise <date>`)

- **Output format so far:** mobile web page, ONE FIXED ARTIFACT updated every day: https://claude.ai/artifact/VLf13N3XA4WML4kZ8L9xDr — title "Napi szentmise", shared "Anyone with the link".
  - History: v1–2 Avilai Szent Teréz 10-15 (EP III); v3 Szent Hedvig 10-16 (EP II); v4 Évközi 29. vasárnap 10-18 (dropdowns); v5 Votív mise a szent angyalokról 10-20 (EP I default, all 4 EPs); v6 + Latin–Hungarian section; v7 light/dark toggle; v8 hidden top bar + floating ☰ button; v9 theme toggle moved into toolbar (☾/☀); v10 ↻ refresh button in toolbar.

- **INSTALLABLE APP (PWA):** `build_pwa.py` → `index.html` (manifest, theme-color, SW registration with `updateViaCache:'none'` + update on visibility, slimmer landscape bar), `manifest.webmanifest` (`display=fullscreen`), `sw.js` (network-first, navigations `cache:'no-store'`, offline fallback), icons (white cross on `#a3171b`). GitHub Pages CDN may serve old version ~10 min.
  - **SECURITY (review 2026-10-19):** no third-party JS; fonts self-hosted (Alegreya/Alegreya SC, OFL); CSP `default-src 'self'` (inline script/style allowed), `object-src`/`base-uri`/`form-action` none; referrer `no-referrer`; SW only same-origin GETs, caches only ok/basic responses; localStorage only text size + theme. Verified: zero external requests, ő/ű fonts load, works offline. Advised: GitHub 2FA; copyright of liturgical texts (MKPK) for a public site.

- **Generator DSL:** `h/h2/p/n/v/r/src/sub/c`; `select/opt/end_opt/end_select`; `ep_select(default, saint=None)`; `EP2_PREFACE`, `EP4_PREFACE`; bilingual `bh/bh2/bp/bn/bv/bc/br/bsrc` with ready pairs (`bi_greeting_penitential`, `COLLECT_END`, `bi_gospel_dialogue`, `bi_gifts`, `bi_preface_dialogue`, `bi_sanctus`, `bi_ep1`, `bi_communion_rite`, `bi_concluding`). Content files start with `exec(open(COMMON).read())` (`COMMON` set by `page.py` in the repo version) and end with `# ---------- RENDER`.
  - Toolbar (hidden; floating ☰ bottom-right): A−, A+, ☾/☀, ↻, section links. Top of page: "Latin–magyar szöveg ↓"; back buttons "↑ Vissza a magyar szöveghez".
  - Latin sources: Missale Romanum 2002 on clerus.org/bibliaclerusonline/en/gl0..gl5.htm; Ordo Missae/EPs/prefaces on ordo.pallotyni.pl; Nova Vulgata on vatican.va. Psalm response/Alleluia Latin not verified against Lectionarium.

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
