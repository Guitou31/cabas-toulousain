"""Photos libres de Wikimedia Commons pour les recettes.

  python tools/commons_fetch.py search "cassoulet" [--limit 12]
      -> liste JSON de candidats (titre, vignette, dimensions, licence, auteur, description, page)
  python tools/commons_fetch.py get "File:Cassoulet.jpg" <id-recette> [--quality exact|proche] [--note "..."]
      -> télécharge la vignette 640 px dans app/img/<id-recette>.<ext> et écrit data/images/<id-recette>.json
         (titre, auteur, licence, lien, qualité). Refuse les licences non libres (NC, ND, tous droits réservés).
"""
import json, os, re, sys, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, 'app', 'img')
META = os.path.join(BASE, 'data', 'images')
API = 'https://commons.wikimedia.org/w/api.php'
UA = 'CabasToulousain/1.0 (https://www.fenelion.fr/cabas-toulousain/; outil non commercial)'


def api(params):
    params = dict(params, format='json', formatversion='2')
    req = urllib.request.Request(API + '?' + urllib.parse.urlencode(params), headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def strip_html(s):
    s = re.sub(r'<[^>]+>', '', s or '')
    return re.sub(r'\s+', ' ', s).strip()


def licence_ok(short):
    s = (short or '').lower()
    if not s:
        return False
    if 'nc' in s.split() or '-nc' in s or ' nc' in s or '-nd' in s or ' nd' in s:
        return False
    return s.startswith('cc by') or s.startswith('cc-by') or s in ('cc0', 'public domain', 'pd') or 'public domain' in s or s.startswith('cc0')


def infos(page):
    ii = (page.get('imageinfo') or [{}])[0]
    em = ii.get('extmetadata') or {}
    def v(k):
        return (em.get(k) or {}).get('value')
    return {
        'titre': page.get('title'),
        'page': 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(page.get('title', '').replace(' ', '_')),
        'vignette': ii.get('thumburl'),
        'largeur': ii.get('width'), 'hauteur': ii.get('height'), 'mime': ii.get('mime'),
        'licence': strip_html(v('LicenseShortName')),
        'licenceUrl': v('LicenseUrl'),
        'auteur': strip_html(v('Artist'))[:120],
        'credit': strip_html(v('Credit'))[:120],
        'description': strip_html(v('ImageDescription'))[:220],
        'licenceLibre': licence_ok(strip_html(v('LicenseShortName'))),
    }


def search(q, limit):
    data = api({'action': 'query', 'generator': 'search', 'gsrsearch': q + ' filetype:bitmap', 'gsrnamespace': 6,
                'gsrlimit': limit, 'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata', 'iiurlwidth': 320,
                'iiextmetadatafilter': 'LicenseShortName|LicenseUrl|Artist|Credit|ImageDescription'})
    pages = (data.get('query') or {}).get('pages') or []
    out = [infos(p) for p in pages]
    out = [o for o in out if o['mime'] in ('image/jpeg', 'image/png', 'image/webp')]
    out.sort(key=lambda o: (not o['licenceLibre'], -(o['largeur'] or 0)))
    return out


def get(title, rid, quality, note):
    if not title.startswith('File:'):
        title = 'File:' + title
    data = api({'action': 'query', 'titles': title, 'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata',
                'iiurlwidth': 640, 'iiextmetadatafilter': 'LicenseShortName|LicenseUrl|Artist|Credit|ImageDescription'})
    pages = (data.get('query') or {}).get('pages') or []
    if not pages or pages[0].get('missing'):
        raise SystemExit('fichier introuvable : ' + title)
    o = infos(pages[0])
    if not o['licenceLibre']:
        raise SystemExit('LICENCE REFUSÉE (%s) pour %s — choisir une autre photo' % (o['licence'] or 'inconnue', title))
    if not o['vignette']:
        raise SystemExit('pas de vignette pour ' + title)
    ext = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}.get(o['mime'], 'jpg')
    os.makedirs(IMG, exist_ok=True); os.makedirs(META, exist_ok=True)
    dest = os.path.join(IMG, rid + '.' + ext)
    req = urllib.request.Request(o['vignette'], headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, 'wb') as f:
        f.write(r.read())
    for e in ('jpg', 'png', 'webp'):
        p = os.path.join(IMG, rid + '.' + e)
        if e != ext and os.path.exists(p):
            os.remove(p)
    meta = {'id': rid, 'fichier': rid + '.' + ext, 'titre': o['titre'], 'page': o['page'], 'auteur': o['auteur'] or o['credit'] or 'auteur non renseigné',
            'licence': o['licence'], 'licenceUrl': o['licenceUrl'], 'qualite': quality, 'note': note, 'description': o['description']}
    with open(os.path.join(META, rid + '.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(json.dumps({'ok': True, 'fichier': dest, 'octets': os.path.getsize(dest), 'licence': o['licence'], 'auteur': meta['auteur']}, ensure_ascii=False))


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] not in ('search', 'get'):
        raise SystemExit(__doc__)
    if a[0] == 'search':
        limit = int(a[a.index('--limit') + 1]) if '--limit' in a else 12
        for o in search(a[1], limit):
            print(json.dumps(o, ensure_ascii=False))
    else:
        quality = a[a.index('--quality') + 1] if '--quality' in a else 'exact'
        note = a[a.index('--note') + 1] if '--note' in a else ''
        get(a[1], a[2], quality, note)
