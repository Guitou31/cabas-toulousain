/* Le Cabas Toulousain — cache hors ligne. Version : 033029c454 */
var VERSION = 'cabas-033029c454';
var SHELL = ['./', './index.html', './data.json', './manifest.webmanifest',
  './icons/icon-192.png', './icons/icon-512.png', './icons/icon-512-maskable.png', './icons/icon-180.png', './icons/icon-32.png'];

self.addEventListener('install', function (e) {
  /* cache:'reload' : on contourne le cache HTTP du navigateur pour ne jamais figer une ancienne version */
  e.waitUntil(caches.open(VERSION).then(function (c) {
    return c.addAll(SHELL.map(function (u) { return new Request(u, { cache: 'reload' }) }));
  }).then(function () { return self.skipWaiting() }));
});
self.addEventListener('activate', function (e) {
  /* on ne supprime que nos propres caches : l'origine github.io peut héberger d'autres applications */
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf('cabas-') === 0 && k !== VERSION && k !== VERSION + '-ext' }).map(function (k) { return caches.delete(k) }));
  }).then(function () { return self.clients.claim() }));
});
self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  var url = new URL(e.request.url);
  if (url.origin === self.location.origin) {
    /* fichiers du site : réponse du cache tout de suite, mise à jour en arrière-plan */
    e.respondWith(caches.open(VERSION).then(function (c) {
      return c.match(e.request, { ignoreSearch: true }).then(function (cached) {
        var net = fetch(e.request).then(function (r) { if (r && r.ok) c.put(e.request, r.clone()); return r }).catch(function () { return cached });
        if (cached) e.waitUntil(net.catch(function () {}));   /* la mise à jour en arrière-plan doit aboutir avant l'arrêt du SW */
        return cached || net;
      });
    }));
  } else if (/cdnjs\.cloudflare\.com|fonts\.googleapis\.com|fonts\.gstatic\.com/.test(url.host)) {
    /* polices et bibliothèque QR : cache d'abord, réseau sinon */
    e.respondWith(caches.open(VERSION + '-ext').then(function (c) {
      return c.match(e.request).then(function (cached) {
        if (cached) return cached;
        return fetch(e.request).then(function (r) { if (r && (r.ok || r.type === 'opaque')) c.put(e.request, r.clone()); return r });
      });
    }));
  }
});
