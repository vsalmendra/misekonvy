// Napi szentmise – offline cache. Network first, so a new day's text appears as soon as it is online.
const CACHE = 'szentmise-5042c378a6';
const CORE = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png', './data/calendar.json', './data/ordinary.json', './data/days.json'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE.map(u => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
// Same-origin files are always fetched from the origin, past every cache: the browser's (no-store)
// and GitHub Pages' CDN (a changing query parameter; the CDN keeps a copy for ~10 minutes otherwise).
// The offline copy is stored under the plain address. Other origins (fonts) go through unchanged.
function fresh(req) {
  const u = new URL(req.url);
  if (u.origin !== self.location.origin) return fetch(req);
  u.searchParams.set('_', Date.now());
  return fetch(u.href, { cache: 'no-store', credentials: 'same-origin' });
}
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const u = new URL(e.request.url);
  // version.json is never answered from the cache: offline it must fail, so the page never reloads offline
  if (u.pathname.endsWith('/version.json')) return;
  const key = u.origin === self.location.origin ? u.origin + u.pathname : e.request;
  e.respondWith(fresh(e.request).then(r => {
    if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(key, copy)); }
    return r;
  }).catch(() => caches.match(key, { ignoreSearch: true }).then(m => m || caches.match('./index.html'))));
});
