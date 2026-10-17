"""Génère le site installable (PWA) dans docs/ à partir de app/index.html et app/data.json :
- docs/index.html : document complet (doctype, head, manifeste, icônes, reset identique à l'artifact)
- docs/manifest.webmanifest, docs/sw.js (cache hors ligne, versionné par empreinte du contenu)
- docs/icons/*.png : icônes dessinées en Python pur (aucune dépendance)
Option : pwa.config.json à la racine, {"url": "https://<compte>.github.io/<depot>/"} pour renseigner PWA_URL
(utile à l'artifact claude.ai pour afficher un QR qui ouvre la version installable)."""
import hashlib, json, math, os, re, struct, zlib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, 'app', 'index.html')
DATA = os.path.join(BASE, 'app', 'data.json')
OUT = os.path.join(BASE, 'docs')
CFG = os.path.join(BASE, 'pwa.config.json')

cfg = {}
if os.path.exists(CFG):
    with open(CFG, encoding='utf-8-sig') as f:
        cfg = json.load(f)
PWA_URL = cfg.get('url', '')

DESCRIPTION = ("Planification des repas et liste de courses privilégiant les produits du grand Sud "
               "(ou d'Occitanie, ou de France), les fruits et légumes de saison et les pâtes et riz complets.")

# ---------- index.html ----------
with open(SRC, encoding='utf-8') as f:
    html = f.read()
m = re.search(r'<title>(.*?)</title>\n', html)
title = m.group(1)
html = html.replace(m.group(0), '', 1)
m = re.search(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com[^>]*>\n', html)
fonts = m.group(0)
html = html.replace(fonts, '', 1)
assert "var PWA_URL = '';" in html, 'PWA_URL introuvable dans app/index.html'
html = html.replace("var PWA_URL = '';", 'var PWA_URL = %s;' % json.dumps(PWA_URL), 1)

head = f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{DESCRIPTION}">
<meta name="theme-color" content="#a84b2c" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#201a17" media="(prefers-color-scheme: dark)">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" sizes="32x32" href="icons/icon-32.png">
<link rel="apple-touch-icon" href="icons/icon-180.png">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Cabas">
{fonts}<style>:root{{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}body{{margin:0;font:14px system-ui,sans-serif}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
</head>
<body>
'''
page = head + html + '\n</body>\n</html>\n'

os.makedirs(os.path.join(OUT, 'icons'), exist_ok=True)
with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(page)
with open(DATA, encoding='utf-8') as f:
    data = f.read()
with open(os.path.join(OUT, 'data.json'), 'w', encoding='utf-8') as f:
    f.write(data)
with open(os.path.join(OUT, '.nojekyll'), 'w') as f:
    f.write('')

# ---------- manifeste ----------
manifest = {
    'name': title, 'short_name': 'Cabas', 'description': DESCRIPTION, 'lang': 'fr',
    'start_url': './', 'scope': './', 'display': 'standalone',
    'background_color': '#f7f3f0', 'theme_color': '#a84b2c',
    'icons': [
        {'src': 'icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
        {'src': 'icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
        {'src': 'icons/icon-512-maskable.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
    ],
}
with open(os.path.join(OUT, 'manifest.webmanifest'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)

# ---------- service worker ----------
version = hashlib.sha1((page + data).encode('utf-8')).hexdigest()[:10]
sw = r'''/* Le Cabas Toulousain — cache hors ligne. Version : __VERSION__ */
var VERSION = 'cabas-__VERSION__';
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
'''.replace('__VERSION__', version)
with open(os.path.join(OUT, 'sw.js'), 'w', encoding='utf-8') as f:
    f.write(sw)

# ---------- icônes (PNG écrits à la main, dessin par échantillonnage) ----------
BRIQUE = (168, 75, 44)
CREME = (255, 246, 241)
VERT = (140, 199, 148)
FONCE = (120, 50, 28)


def png(width, height, rows):
    def chunk(tag, payload):
        c = struct.pack('>I', len(payload)) + tag + payload
        return c + struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(r) for r in rows)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def couleur(x, y, maskable):
    """Couleur (r,g,b,a) au point (x,y) en coordonnées 0..1 : fond brique arrondi, cabas crème, feuille verte."""
    # fond : carré arrondi (ou plein pour l'icône maskable)
    if not maskable:
        r = 0.22
        dx = max(abs(x - 0.5) - (0.5 - r), 0.0)
        dy = max(abs(y - 0.5) - (0.5 - r), 0.0)
        if math.hypot(dx, dy) > r:
            return (0, 0, 0, 0)
    col = BRIQUE
    # corps du cabas : trapèze évasé vers le haut, coins du bas arrondis
    top, bottom = 0.44, 0.80
    if top <= y <= bottom:
        w = 0.235 - (y - top) / (bottom - top) * 0.035
        if abs(x - 0.5) <= w:
            # arrondi des coins bas
            cy = bottom - 0.05
            if y > cy and abs(x - 0.5) > w - 0.05:
                if math.hypot(abs(x - 0.5) - (w - 0.05), y - cy) <= 0.05:
                    col = CREME
            else:
                col = CREME
    # rabat (bande plus sombre en haut du sac)
    if col == CREME and top <= y <= top + 0.045:
        col = (236, 214, 203)
    # anse : demi-anneau au-dessus de l'ouverture
    d = math.hypot(x - 0.5, y - top)
    if y <= top + 0.01 and 0.135 <= d <= 0.18:
        col = CREME
    # feuille verte qui dépasse du sac (ellipse inclinée)
    ex, ey = x - 0.615, y - 0.37
    a = math.radians(-40)
    rx = ex * math.cos(a) - ey * math.sin(a)
    ry = ex * math.sin(a) + ey * math.cos(a)
    if (rx / 0.085) ** 2 + (ry / 0.038) ** 2 <= 1.0:
        col = VERT
        if abs(ry) < 0.006 and rx > -0.07:
            col = (90, 150, 100)
    return col + (255,)


def rendu(size, maskable=False, ss=3):
    rows = []
    for py in range(size):
        row = []
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    x = (px + (sx + 0.5) / ss) / size
                    y = (py + (sy + 0.5) / ss) / size
                    c = couleur(x, y, maskable)
                    for i in range(4):
                        acc[i] += c[i]
            n = ss * ss
            row.extend(int(round(v / n)) for v in acc)
        rows.append(row)
    return png(size, size, rows)


for nom, size, mask in (('icon-512', 512, False), ('icon-512-maskable', 512, True), ('icon-192', 192, False),
                        ('icon-180', 180, False), ('icon-32', 32, False)):
    with open(os.path.join(OUT, 'icons', nom + '.png'), 'wb') as f:
        f.write(rendu(size, mask, ss=3 if size >= 180 else 4))

print('site généré dans', OUT, '| version SW', version, '| PWA_URL =', PWA_URL or '(non renseignée)')
print('fichiers :', sorted(os.listdir(OUT)), '+', sorted(os.listdir(os.path.join(OUT, 'icons'))))
