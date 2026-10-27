// Browser test of the app's day selection and reload behaviour. Runs before every deploy.
//
//   npm i --no-save playwright@1.56.1 && npx playwright install chromium   (once)
//   python3 tools/build.py && node tests/app-test.mjs
//
// CHROMIUM_PATH may point to an existing Chromium. Dates come from app/data/calendar.json, so the
// test keeps working as masses are added. "Today" is faked inside the page.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const APP = fileURLToPath(new URL('../app/', import.meta.url));
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };

const server = createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^(\.\.[/\\])+/, '');
  try {
    const body = await readFile(join(APP, path.endsWith('/') ? path + 'index.html' : path));
    res.writeHead(200, { 'content-type': TYPES[extname(path)] || 'text/html' }).end(body);
  } catch { res.writeHead(404).end(); }
}).listen(0);
const BASE = `http://localhost:${server.address().port}/`;

const cal = JSON.parse(await readFile(join(APP, 'data/calendar.json'), 'utf8')).masses;
const dates = cal.map(m => m.date).sort();
const first = dates[0], last = dates.at(-1);
const shift = (d, n) => { const x = new Date(d + 'T12:00:00Z'); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().slice(0, 10); };
const gap = (() => { for (let d = shift(first, 1); d < last; d = shift(d, 1)) if (!dates.includes(d)) return d; return null; })();

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
let failures = 0;
function check(ok, what) { console.log(`${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) failures++; }

// A page whose clock says `day` 08:00 local time; ctx.clock.setSystemTime moves it (app resumed next day).
async function open(day, path = '', { blockCalendar = false, blockOrdinary = false } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  // Playwright's clock: the faked date survives reloads, like a real phone's date.
  await ctx.clock.install({ time: new Date(day + 'T08:00:00') });
  if (blockCalendar) await ctx.route('**/data/calendar.json', r => r.abort());
  if (blockOrdinary) await ctx.route('**/data/ordinary.json', r => r.abort());
  const page = await ctx.newPage();
  const loads = [], errors = [];
  page.on('request', r => { if (r.resourceType() === 'document') loads.push(r.url().replace(BASE, '/')); });
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(BASE + path);
  await page.waitForTimeout(1500);
  const state = async () => ({
    // no Mass of the day: the Order of Mass alone ("ordinary") or, if that fails too, the logo ("empty")
    empty: await page.evaluate(() => ['ordinary', 'empty'].some(c => document.body.classList.contains(c))),
    ordinary: await page.evaluate(() => document.body.classList.contains('ordinary')),
    logo: await page.evaluate(() => document.body.classList.contains('empty')),
    title: await page.textContent('#m-title'),
  });
  const setDay = d => ctx.clock.setSystemTime(new Date(d + 'T08:00:00'));
  return { ctx, page, loads, errors, state, setDay };
}

// 1. A day with a Mass opens it, without any reload.
{
  const t = await open(last);
  const s = await t.state();
  check(!s.empty && s.title === cal.find(m => m.date === last).title, `${last}: opens "${s.title}"`);
  check(t.loads.length === 1, `${last}: no reload (${t.loads.length} page load)`);
  check(t.errors.length === 0, `${last}: no script errors ${t.errors.join(' ')}`);
  // The date picker offers exactly the days in the calendar.
  await t.page.click('#menu-fab'); await t.page.click('#pick-date');
  const months = new Set(dates.map(d => d.slice(0, 7)));
  let offered = await t.page.$$eval('#cal-grid button.has', b => b.length);
  for (let i = 1; i < months.size; i++) { await t.page.click('#cal-prev'); offered += await t.page.$$eval('#cal-grid button.has', b => b.length); }
  check(offered === dates.length, `date picker offers ${offered} of ${dates.length} days`);
  await t.ctx.close();
}

// 2. After the last Mass: exactly one automatic fresh reload, then the logo; the button reloads once more, no loop.
{
  const day = shift(last, 3);
  const t = await open(day);
  await t.page.waitForTimeout(2000);
  const s = await t.state();
  check(s.ordinary, `${day} (after last): Order of Mass shown`);
  const prefs = await t.page.$$eval('#sel-pref option', o => o.map(x => x.value));
  const eps = await t.page.$$eval('#sel-ep option', o => o.map(x => x.value));
  check(prefs.join() === 'ep2,ep4' && eps.length === 4, `${day}: prefaces ${prefs.join(', ')}; ${eps.length} Eucharistic prayers`);
  check(await t.page.isVisible('#empty-reload') && await t.page.isVisible('#latin'), `${day}: reload button and Latin section present`);
  check(t.loads.length === 2, `${day}: exactly one automatic reload (${t.loads.join(' → ')})`);
  check(t.loads.every(u => u === '/') && t.page.url() === BASE, `${day}: the address never changes`);
  await t.page.click('#empty-reload');
  await t.page.waitForTimeout(2500);
  check(t.loads.length === 3, `${day}: "Újratöltés" reloads exactly once (${t.loads.length} page loads)`);
  check((await t.state()).ordinary, `${day}: still the Order of Mass after the manual reload`);
  check(t.errors.length === 0, `${day}: no script errors ${t.errors.join(' ')}`);
  await t.ctx.close();
}

// 3. Before the first Mass, and a gap between masses: logo, no automatic reload.
for (const day of [shift(first, -1), gap].filter(Boolean)) {
  const t = await open(day);
  check((await t.state()).empty && t.loads.length === 1, `${day} (no Mass, not after the last): Order of Mass, no reload`);
  await t.ctx.close();
}

// 4. No URL tricks: a ?d= in the address is ignored; the device date decides.
{
  const t = await open(last, `?d=${first}`);
  const s = await t.state();
  check(s.title === cal.find(m => m.date === last).title && t.loads.length === 1, `?d=${first} ignored: today's Mass opens ("${s.title}")`);
  await t.ctx.close();
}

// 4b. Days without a Mass: the Order of Mass with the readings of the liturgical day (days.json ->
//     cycle/<key>.json) — a day of this year, and one of a later year reusing them.
{
  const days = JSON.parse(await readFile(join(APP, 'data/days.json'), 'utf8'));
  const candidates = Object.keys(days).filter(d => d > last && days[d][1] && !dates.includes(d));
  const later = candidates.find(d => d.slice(0, 4) > last.slice(0, 4)) || candidates.at(-1);
  for (const day of [candidates[0], later].filter(Boolean)) {
    const t = await open(day);
    await t.page.waitForTimeout(800);
    const text = await t.page.innerText('#r2');
    const meta = await t.page.textContent('#m-meta');
    check((await t.state()).ordinary && !text.includes('lekcionáriumból') && text.includes('Ez az Isten igéje') && meta === days[day][0],
      `${day}: Order of Mass with the readings of "${meta}" (${days[day][1]})`);
    await t.ctx.close();
  }
}

// 5. Calendar cannot be loaded (offline, no copy): logo, no automatic reload.
{
  const t = await open(last, '', { blockCalendar: true });
  check((await t.state()).empty && t.loads.length === 1, 'calendar unreachable: Order of Mass, no reload');
  await t.ctx.close();
}

// 5b. Neither the calendar nor the Order of Mass can be loaded: the logo with the reload button.
{
  const t = await open(last, '', { blockCalendar: true, blockOrdinary: true });
  const s = await t.state();
  check(s.logo && await t.page.isVisible('#empty-reload') && t.loads.length === 1, 'nothing loadable: logo with reload, no automatic reload');
  await t.ctx.close();
}

// 6. Installed app resumed on a new day: follows the date; after the last Mass it reloads only once.
{
  const t = await open(last);
  const next = shift(last, 1);
  await t.setDay(next);
  await t.page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await t.page.waitForTimeout(2500);
  check((await t.state()).empty, `resumed on ${next}: Order of Mass`);
  check(t.loads.length === 2, `resumed on ${next}: one reload only (${t.loads.join(' → ')})`);
  await t.page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await t.page.waitForTimeout(1500);
  check(t.loads.length === 2, `resumed again on ${next}: no further reload`);
  await t.ctx.close();
}
if (dates.length > 1) {
  const [a, b] = dates.slice(-2);
  const t = await open(a);
  await t.setDay(b);
  await t.page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await t.page.waitForTimeout(1500);
  const s = await t.state();
  check(s.title === cal.find(m => m.date === b).title && t.loads.length === 1, `resumed from ${a} on ${b}: shows ${b}, no reload`);
  await t.ctx.close();
}

await browser.close();
server.close();
console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed');
process.exit(failures ? 1 : 0);
