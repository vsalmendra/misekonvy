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
async function open(day, path = '', { blockCalendar = false } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  // Playwright's clock: the faked date survives reloads, like a real phone's date.
  await ctx.clock.install({ time: new Date(day + 'T08:00:00') });
  if (blockCalendar) await ctx.route('**/data/calendar.json', r => r.abort());
  const page = await ctx.newPage();
  const loads = [], errors = [];
  page.on('request', r => { if (r.resourceType() === 'document') loads.push(r.url().replace(BASE, '/')); });
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(BASE + path);
  await page.waitForTimeout(1500);
  const state = async () => ({
    empty: await page.evaluate(() => document.body.classList.contains('empty')),
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
  check(s.empty, `${day} (after last): logo screen`);
  check(t.loads.length === 2 && t.loads[1].includes(`frissitve=${day}`), `${day}: exactly one automatic reload (${t.loads.join(' → ')})`);
  check(!t.page.url().includes('frissitve'), `${day}: marker removed from the address`);
  await t.page.click('#empty-reload');
  await t.page.waitForTimeout(2500);
  check(t.loads.length === 3, `${day}: "Újratöltés" reloads exactly once (${t.loads.length} page loads)`);
  check((await t.state()).empty, `${day}: still the logo after the manual reload`);
  check(t.errors.length === 0, `${day}: no script errors ${t.errors.join(' ')}`);
  await t.ctx.close();
}

// 3. Before the first Mass, and a gap between masses: logo, no automatic reload.
for (const day of [shift(first, -1), gap].filter(Boolean)) {
  const t = await open(day);
  check((await t.state()).empty && t.loads.length === 1, `${day} (no Mass, not after the last): logo, no reload`);
  await t.ctx.close();
}

// 4. ?d= opens that day, whatever today is.
{
  const t = await open(shift(last, 10), `?d=${first}`);
  const s = await t.state();
  check(!s.empty && t.loads.length === 1, `?d=${first}: opens "${s.title}" without reload`);
  await t.ctx.close();
}

// 5. Calendar cannot be loaded (offline, no copy): logo, no automatic reload.
{
  const t = await open(last, '', { blockCalendar: true });
  check((await t.state()).empty && t.loads.length === 1, 'calendar unreachable: logo, no reload');
  await t.ctx.close();
}

// 6. Installed app resumed on a new day: follows the date; after the last Mass it reloads only once.
{
  const t = await open(last);
  const next = shift(last, 1);
  await t.setDay(next);
  await t.page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await t.page.waitForTimeout(2500);
  check((await t.state()).empty, `resumed on ${next}: logo`);
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
