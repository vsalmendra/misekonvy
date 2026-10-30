// Browser test of the app's day selection and automatic update (reload) behaviour. Runs before every deploy.
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
async function open(day, path = '', { blockCalendar = false, blockOrdinary = false, version, time = '08:00' } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  // Playwright's clock: the faked date survives reloads, like a real phone's date.
  await ctx.clock.install({ time: new Date(`${day}T${time}:00`) });
  if (blockCalendar) await ctx.route('**/data/calendar.json', r => r.abort());
  if (blockOrdinary) await ctx.route('**/data/ordinary.json', r => r.abort());
  // version.json as the server would answer it: the real file, or a newer build ("new"), or offline (null)
  let served = version;
  await ctx.route('**/version.json?*', r => served === undefined ? r.continue() : served === null ? r.abort() : r.fulfill({ json: { build: served } }));
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
  const setDay = (d, t = '08:00') => ctx.clock.setSystemTime(new Date(`${d}T${t}:00`));
  const resume = async (ms = 1500) => { await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange'))); await page.waitForTimeout(ms); };
  const serve = v => { served = v; };
  return { ctx, page, loads, errors, state, setDay, resume, serve };
}

// 1. A day with a Mass opens it, without any reload.
{
  const t = await open(last);
  const s = await t.state();
  check(!s.empty && s.title === cal.find(m => m.date === last).title, `${last}: opens "${s.title}"`);
  check(t.loads.length === 1, `${last}: no reload (${t.loads.length} page load)`);
  check(t.errors.length === 0, `${last}: no script errors ${t.errors.join(' ')}`);
  // The Eucharistic prayer can be chosen in the Latin section too; both dropdowns stay in step.
  await t.page.selectOption('#sel-ep-la', '2');
  const shown = await t.page.$$eval('#latin .variants[data-group="ep"] > .variant:not([hidden])', v => v.map(x => x.dataset.opt));
  check(await t.page.$eval('#sel-ep', s => s.value) === '2' && shown.join() === '2', 'Latin EP dropdown switches the prayer and the Hungarian dropdown');
  // The date picker offers exactly the days in the calendar.
  await t.page.click('#menu-fab'); await t.page.click('#pick-date');
  const months = new Set(dates.map(d => d.slice(0, 7)));
  let offered = await t.page.$$eval('#cal-grid button.has', b => b.length);
  for (let i = 1; i < months.size; i++) { await t.page.click('#cal-prev'); offered += await t.page.$$eval('#cal-grid button.has', b => b.length); }
  check(offered === dates.length, `date picker offers ${offered} of ${dates.length} days`);
  await t.page.click('#cal-close');
  // Jump lists: "Magyar" lists the Hungarian parts and jumps to the gospel; "Latin–magyar" the bilingual ones.
  await t.page.click('#menu-fab'); await t.page.click('#toc-open');
  check(await t.page.$eval('#toc-mode-hu', b => b.getAttribute('aria-pressed')) === 'true', 'jump list opens on "Magyar" at the top of the page');
  const hu = await t.page.$$eval('#toc-list button .t', b => b.map(x => x.firstChild.textContent));
  check(hu.length > 20 && ['Bevezető szertartás', 'Evangélium', 'Hitünk titka', 'Áldozás'].every(x => hu.includes(x)), `"Magyar" jump list: ${hu.length} entries`);
  await t.page.click('#toc-list button:has-text("Evangélium")');
  const top = await t.page.evaluate(() => [...document.querySelectorAll('#r2 h3')].find(h => h.textContent === 'Evangélium').getBoundingClientRect().top);
  check(!(await t.page.$eval('#toc', d => d.open)) && Math.abs(top - 12) < 3, `jump to the gospel (heading at ${Math.round(top)}px)`);
  await t.page.click('#menu-fab'); await t.page.click('#toc-open'); await t.page.click('#toc-mode-la');
  const la = await t.page.$$eval('#toc-list button .la', b => b.map(x => x.textContent));
  check(la.includes('Collecta') && la.includes('Oratio universalis'), `"Latin–magyar" jump list: ${la.length} entries with Latin names`);
  // Home: back to the top
  await t.page.click('#toc-top');
  check(!(await t.page.$eval('#toc', d => d.open)) && await t.page.evaluate(() => window.scrollY) === 0, '"Az elejére" goes back to the top');
  // No Latin equivalent: blank Latin column with a short note, the Hungarian text is there.
  const note = await t.page.$$eval('#latin .la-note', n => n.map(x => x.textContent));
  const hupet = await t.page.$$eval('#latin h3.bi-r', h => h.some(x => x.textContent === 'Egyetemes könyörgések' && x.nextElementSibling.nextElementSibling?.textContent.length > 20));
  check(note.includes('Nincs latin megfelelője.') && hupet, 'prayer of the faithful in the bilingual section: Hungarian text, Latin blank with a note');
  // Portrait: one column per screen; the arrow at the middle of the edge slides to the other column.
  check(!(await t.page.isVisible('#bi-switch')), 'column arrow hidden outside the Latin–magyar section');
  await t.page.evaluate(() => { const h = [...document.querySelectorAll('#latin h3.bi-r')].find(x => x.textContent === 'Könyörgés'); window.scrollTo(0, h.getBoundingClientRect().top + scrollY - 100); });
  await t.page.waitForTimeout(300);
  const colw = await t.page.$eval('#latin .bi-grid', g => [g.clientWidth, g.querySelector('.bi-l:not(.bi-full)').getBoundingClientRect().width]);
  check(await t.page.isVisible('#bi-switch') && Math.abs(colw[0] - colw[1]) < 2, `portrait: one column per screen (${colw.join(' / ')}px), arrow shown`);
  await t.page.click('#bi-switch'); await t.page.waitForTimeout(900);
  const atHu = await t.page.$eval('#latin .bi-grid', g => g.scrollLeft >= g.scrollWidth - g.clientWidth - 2);
  check(atHu && await t.page.$eval('#bi-switch', b => b.classList.contains('left')), 'arrow slides to the Hungarian column and moves to the left edge');
  await t.ctx.close();
}

// 2. After the last Mass: the Order of Mass, no automatic reload (the version is the same); the button reloads once.
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
  check(t.loads.length === 1, `${day}: no automatic reload (${t.loads.join(' → ')})`);
  check(t.loads.every(u => u === '/') && t.page.url() === BASE, `${day}: the address never changes`);
  await t.page.click('#empty-reload');
  await t.page.waitForTimeout(2500);
  check(t.loads.length === 2, `${day}: "Újratöltés" reloads exactly once (${t.loads.length} page loads)`);
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
    const laText = await t.page.innerText('#latin');
    check(laText.includes('Latinul még nincs feltöltve.') && laText.includes('Ez az Isten igéje'), `${day}: bilingual readings in Hungarian, Latin blank with a note`);
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

// 6. Installed app resumed on a new day: follows the date, without reloading (same version).
{
  const t = await open(last);
  const next = shift(last, 1);
  await t.setDay(next);
  await t.page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await t.page.waitForTimeout(2500);
  check((await t.state()).empty, `resumed on ${next}: Order of Mass`);
  check(t.loads.length === 1, `resumed on ${next}: no reload (${t.loads.join(' → ')})`);
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

// 7. Automatic update: a newer version on the server reloads the page once; if the old page is still
//    served after the reload (CDN), no further reload for 15 minutes, then one more try. No loop.
{
  const t = await open(last, '', { version: 'new' });
  await t.page.waitForTimeout(1500);
  check(t.loads.length === 2, `new version: exactly one automatic reload (${t.loads.length} page loads)`);
  await t.resume();
  check(t.loads.length === 2, 'new version, old page still served: resumed, no further reload');
  await t.ctx.clock.setSystemTime(new Date(Date.parse(last + 'T08:00:00') + 16 * 60 * 1000));
  await t.resume(2500);
  check(t.loads.length === 3, `16 minutes later, resumed: one more try (${t.loads.length} page loads)`);
  await t.resume();
  check(t.loads.length === 3, 'resumed again at once: no further reload');
  check(t.errors.length === 0, `update: no script errors ${t.errors.join(' ')}`);
  await t.ctx.close();
}

// 7b. Offline (version.json not loadable): never reloads.
{
  const t = await open(last, '', { version: null });
  await t.resume();
  check(t.loads.length === 1 && !(await t.state()).empty, 'version unreachable: today\'s Mass, no reload');
  await t.ctx.close();
}

// 7c. Published while the app is open: nothing happens while reading; on resume it reloads, keeping the
//     day that was open (another day chosen in the picker) and the scroll position.
if (dates.length > 1) {
  const other = dates[0];
  const t = await open(last);
  await t.page.click('#menu-fab'); await t.page.click('#pick-date');
  while (!(await t.page.$(`#cal-grid button[data-date="${other}"]`))) await t.page.click('#cal-prev');
  await t.page.click(`#cal-grid button[data-date="${other}"]`);
  await t.page.waitForTimeout(800);
  await t.page.evaluate(() => window.scrollTo(0, 1500));
  t.serve('new');
  await t.page.mouse.wheel(0, 10);          // reading: the version is not checked while the page is in use
  await t.page.waitForTimeout(1000);
  check(t.loads.length === 1, 'new version while reading: no reload');
  const y = await t.page.evaluate(() => window.scrollY);
  await t.resume(2500);
  const s = await t.state();
  const y2 = await t.page.evaluate(() => window.scrollY);
  check(t.loads.length === 2, `new version, resumed: one reload (${t.loads.length} page loads)`);
  check(s.title === cal.find(m => m.date === other).title && Math.abs(y2 - y) < 2, `after the update: ${other} kept ("${s.title}"), scroll ${y2} (was ${y})`);
  await t.ctx.close();
}

// 7d. A slow answer arriving after the reader touched the page: no reload, a button instead; it reloads once.
{
  const t = await open(last, '', { version: undefined });
  await t.ctx.unroute('**/version.json?*');
  await t.ctx.route('**/version.json?*', async r => { await new Promise(s => setTimeout(s, 1000)); await r.fulfill({ json: { build: 'new' } }); });
  await t.resume(100);
  await t.page.mouse.wheel(0, 10);
  await t.page.waitForTimeout(2000);
  check(t.loads.length === 1 && await t.page.isVisible('#update-btn'), 'slow version answer after the reader scrolled: no reload, "Új változat" button');
  await t.page.click('#update-btn');
  await t.page.waitForTimeout(2000);
  check(t.loads.length === 2, `the button reloads once (${t.loads.length} page loads)`);
  // the update log on the device lists what happened
  await t.page.click('#menu-fab'); await t.page.click('#show-log');
  const logText = await t.page.textContent('#log-text');
  check(/indulás \S+ \(/.test(logText) && /olvasás közben → gomb/.test(logText) && /frissítés gombbal/.test(logText), 'update log: launch, check, button');
  await t.ctx.close();
}

// 8. From 19:30 local time the app opens on the next day's Mass; before, on today's.
if (dates.length > 1) {
  const [a, b] = dates.slice(-2);
  const eve = shift(b, -1), title = d => cal.find(m => m.date === d).title;
  const late = await open(eve, '', { time: '19:30' });
  const s1 = await late.state();
  check(s1.title === title(b) && late.loads.length === 1 && !(await late.page.isVisible('#notice')), `${eve} 19:30: opens the next day's Mass ("${s1.title}"), no note`);
  await late.ctx.close();
  const early = await open(eve, '', { time: '19:29' });
  const s2 = await early.state();
  check(eve === a ? s2.title === title(a) : s2.empty, `${eve} 19:29: still today's (${eve === a ? s2.title : 'Order of Mass'})`);
  // resumed in the evening: moves on to tomorrow
  await early.setDay(eve, '20:15');
  await early.resume();
  const s3 = await early.state();
  check(s3.title === title(b) && early.loads.length === 1, `${eve} resumed at 20:15: moves on to ${b} ("${s3.title}")`);
  await early.ctx.close();
}
{
  const day = shift(last, 1);   // evening before a day without a Mass: tomorrow's Order of Mass, tomorrow's date
  const t = await open(last, '', { time: '21:00' });
  const s = await t.state();
  const date = await t.page.textContent('#m-date');
  const [y, m, d] = day.split('-').map(Number);
  check(s.ordinary && date.startsWith(`${y}. `) && date.includes(` ${d}. ·`), `${last} 21:00: Order of Mass of ${day} (${date})`);
  await t.ctx.close();
}

await browser.close();
server.close();
console.log(failures ? `\n${failures} check(s) failed` : '\nall checks passed');
process.exit(failures ? 1 : 0);
