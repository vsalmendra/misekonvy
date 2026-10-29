// Napi szentmise – offline cache. Network first, so a new day's text appears as soon as it is online.
const CACHE = 'szentmise-d359d04038';
const CORE = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png', './data/calendar.json', './data/ordinary.json', './data/days.json'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE.map(u => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  // version.json is never answered from the cache: offline it must fail, so the page never reloads offline
  if (new URL(e.request.url).pathname.endsWith('/version.json')) return;
  const nav = e.request.mode === 'navigate' || e.request.url.endsWith('/index.html');
  e.respondWith(fetch(e.request, nav ? { cache: 'no-store' } : {}).then(r => { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return r; })
    .catch(() => caches.match(e.request, { ignoreSearch: true }).then(m => m || caches.match('./index.html'))));
});
