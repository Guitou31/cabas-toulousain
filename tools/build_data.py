"""Assemble app/data.json depuis les fichiers produits par les agents (v1 + v2) :
v1 : data/ingredients.json, data/verif-1..3.json, data/recettes-*.json, data/mappings.json, data/drive.json
v2 : data/regions.json (catégorie + régions), data/produits-saison.json (fruits & légumes ajoutés),
     data/verif-regions-1..3.json, data/gras-existants.json, data/recettes2-*.json, data/mappings2.json
v3 : data/recettes3-*.json (recettes + nouveauxIngredients + mappings par lot), data/images/<id>.json
Nettoie, applique, valide, et signale tout problème restant."""
import json, os, sys, unicodedata

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(BASE, 'data')
OUT = os.path.join(BASE, 'app', 'data.json')

RAYONS = ['Fruits & Légumes', 'Boucherie & Volaille', 'Poissonnerie',
          'Crèmerie & Fromages', 'Épicerie', 'Épices & Condiments', 'Boulangerie']
RAYON_CAT = {'Fruits & Légumes': 'legume', 'Boucherie & Volaille': 'viande', 'Poissonnerie': 'poisson',
             'Crèmerie & Fromages': 'cremerie', 'Épicerie': 'epicerie', 'Épices & Condiments': 'condiment',
             'Boulangerie': 'feculent'}
CATEGORIES = ['fruit', 'legume', 'viande', 'poisson', 'cremerie', 'feculent', 'epicerie', 'condiment']
TYPES = {'viande': 'viande', 'volaille': 'volaille', 'poisson': 'poisson',
         'vege': 'vege', 'vege': 'vege', 'vegetarien': 'vege', 'vegetarienne': 'vege'}
UNITES = ['g', 'kg', 'ml', 'cl', 'l', 'pièce', 'c. à soupe', 'c. à café',
          'gousse', 'botte', 'tranche', 'boîte', 'pincée', 'sachet']
LABELS = ['AOP', 'IGP', 'Label Rouge', 'STG', 'AB', 'Origine France Garantie']
REGIONS = ['Auvergne-Rhône-Alpes', 'Bourgogne-Franche-Comté', 'Bretagne', 'Centre-Val de Loire', 'Corse',
           'Grand Est', 'Hauts-de-France', 'Île-de-France', 'Normandie', 'Nouvelle-Aquitaine', 'Occitanie',
           'Pays de la Loire', "Provence-Alpes-Côte d'Azur"]

problems = []


def norm(s):
    s = unicodedata.normalize('NFD', str(s or '').strip().lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s


def rkey(s):
    return ''.join(c for c in norm(s) if c.isalnum())


REGION_KEYS = {rkey(r): r for r in REGIONS}
REGION_KEYS.update({'paca': "Provence-Alpes-Côte d'Azur", 'aura': 'Auvergne-Rhône-Alpes',
                    'grandest': 'Grand Est', 'cvl': 'Centre-Val de Loire', 'idf': 'Île-de-France',
                    'bfc': 'Bourgogne-Franche-Comté', 'pdl': 'Pays de la Loire', 'hdf': 'Hauts-de-France',
                    'provencealpescotedazur': "Provence-Alpes-Côte d'Azur"})


def load(name, required=True):
    p = os.path.join(D, name)
    if not os.path.exists(p):
        if required:
            problems.append('FICHIER MANQUANT : ' + name)
        return None
    try:
        with open(p, encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        problems.append('JSON INVALIDE %s : %s' % (name, e))
        return None


def clean_regions(lst, ctx):
    out = []
    for r in (lst or []):
        k = rkey(r)
        if k in REGION_KEYS:
            canon = REGION_KEYS[k]
            if canon not in out:
                out.append(canon)
        else:
            problems.append('région inconnue "%s" sur %s (ignorée)' % (r, ctx))
    return out


def clean_months(lst):
    return sorted(set(int(m) for m in (lst or []) if isinstance(m, (int, float)) and 1 <= int(m) <= 12))


def clean_ing(g):
    if not isinstance(g, dict) or not g.get('id') or not g.get('nom'):
        return None
    siqo = []
    for l in (g.get('siqo') or []):
        if not isinstance(l, dict):
            continue
        lab = str(l.get('label') or '').strip()
        if lab == 'Agriculture Biologique':
            lab = 'AB'
        if lab not in LABELS:
            problems.append('label inconnu "%s" sur %s (retiré)' % (lab, g['id']))
            continue
        siqo.append({'label': lab, 'denomination': l.get('denomination') or None})
    rayon = str(g.get('rayon') or '').strip()
    if rayon not in RAYONS:
        problems.append('rayon inconnu "%s" sur %s -> Épicerie' % (rayon, g['id']))
        rayon = 'Épicerie'
    cat = norm(g.get('categorie') or '')
    if cat not in CATEGORIES:
        cat = None  # attribué plus tard (regions.json) ou dérivé du rayon
    return {
        'id': str(g['id']), 'nom': str(g['nom']), 'rayon': rayon,
        'categorie': cat,
        'origineFrance': bool(g.get('origineFrance')),
        'provenanceLocale': (str(g['provenanceLocale']) if g.get('provenanceLocale') else None),
        'siqo': siqo, 'saisonMois': clean_months(g.get('saisonMois')),
        'risqueEspagne': bool(g.get('risqueEspagne')),
        'conseil': (str(g['conseil']) if g.get('conseil') else None),
        'versionComplete': (str(g['versionComplete']) if g.get('versionComplete') else None),
        'regions': clean_regions(g.get('regions'), g['id']) if g.get('regions') is not None else None,
    }


# ---------- 1. référentiel v1 + corrections v1 ----------
raw = load('ingredients.json') or {}
ings = {}
for g in (raw.get('ingredients') or []):
    c = clean_ing(g)
    if c:
        if c['id'] in ings:
            problems.append('id ingrédient en double : ' + c['id'])
        ings[c['id']] = c
print('ingredients de base :', len(ings))

ncorr = 0
for i in (1, 2, 3):
    v = load('verif-%d.json' % i, required=False)
    if not v:
        continue
    for g in (v.get('corriges') or []):
        c = clean_ing(g)
        if c and c['id'] in ings:
            keep_regions = ings[c['id']].get('regions')
            ings[c['id']] = c
            if c.get('regions') is None:
                ings[c['id']]['regions'] = keep_regions
            ncorr += 1
        elif c:
            problems.append('correction v1 sur id inconnu : ' + c['id'])
print('corrections v1 appliquées :', ncorr)

# nouveaux ingrédients de la synthèse v1
mp1 = load('mappings.json', required=False) or {}
for g in (mp1.get('nouveauxIngredients') or []):
    c = clean_ing(g)
    if c and c['id'] not in ings:
        ings[c['id']] = c

# ---------- 2. v2 : catégories + régions ----------
reg = load('regions.json', required=False) or {}
ntag = 0
for it in (reg.get('items') or []):
    if not isinstance(it, dict) or it.get('id') not in ings:
        if isinstance(it, dict):
            problems.append('regions.json : id inconnu ' + str(it.get('id')))
        continue
    g = ings[it['id']]
    cat = norm(it.get('categorie') or '')
    if cat in CATEGORIES:
        g['categorie'] = cat
    else:
        problems.append('catégorie inconnue "%s" sur %s' % (it.get('categorie'), it['id']))
    g['regions'] = clean_regions(it.get('regions'), it['id'])
    ntag += 1
print('ingrédients catégorisés/régionalisés :', ntag)

prod = load('produits-saison.json', required=False) or {}
nprod = 0
for g in (prod.get('ingredients') or []):
    c = clean_ing(g)
    if c and c['id'] not in ings:
        ings[c['id']] = c
        nprod += 1
    elif c:
        problems.append('produits-saison : id déjà présent, ignoré : ' + c['id'])
print('fruits & légumes ajoutés :', nprod)

ncorr2 = 0
for i in (1, 2, 3):
    v = load('verif-regions-%d.json' % i, required=False)
    if not v:
        continue
    for c in (v.get('corriges') or []):
        if not isinstance(c, dict) or c.get('id') not in ings:
            if isinstance(c, dict):
                problems.append('verif-regions : id inconnu ' + str(c.get('id')))
            continue
        g = ings[c['id']]
        if 'regions' in c:
            g['regions'] = clean_regions(c['regions'], c['id'])
        if 'categorie' in c and norm(c['categorie']) in CATEGORIES:
            g['categorie'] = norm(c['categorie'])
        if 'saisonMois' in c:
            g['saisonMois'] = clean_months(c['saisonMois'])
        if 'risqueEspagne' in c:
            g['risqueEspagne'] = bool(c['risqueEspagne'])
        if 'conseil' in c:
            g['conseil'] = str(c['conseil']) if c['conseil'] else None
        ncorr2 += 1
print('corrections v2 (régions/saisons) appliquées :', ncorr2)

# ---------- 3. mappings v1 + v2, nouveaux ingrédients v2 ----------
mp2 = load('mappings2.json', required=False) or {}
# v3 : chaque lot data/recettes3-<theme>.json porte ses propres nouveauxIngredients et mappings
LOTS3 = ('printemps-ete', 'monde', 'poisson-mer', 'viandes-volailles', 'vege-legumes', 'rapides-famille')
mp3 = [m for m in (load('recettes3-%s.json' % k, required=False) for k in LOTS3) if m]
for src in [mp2] + mp3:
    for g in (src.get('nouveauxIngredients') or []):
        c = clean_ing(g)
        if c and c['id'] not in ings:
            ings[c['id']] = c

# valeurs par défaut
for g in ings.values():
    if not g.get('categorie'):
        g['categorie'] = RAYON_CAT.get(g['rayon'], 'epicerie')
        problems.append('catégorie dérivée du rayon pour ' + g['id'])
    if g.get('regions') is None:
        g['regions'] = []
        if g['origineFrance'] and g['categorie'] in ('fruit', 'legume', 'viande', 'cremerie', 'feculent'):
            problems.append('aucune région pour ingrédient principal français : ' + g['id'])

nom2id = {}
for g in ings.values():
    nom2id.setdefault(norm(g['nom']), g['id'])
mappings = {
    norm('Bouillon de légumes'): 'bouillon-legumes',
    norm('Bouillon de légumes (cube)'): 'bouillon-legumes',
    norm('Amandes effilées'): 'amandes',
}
for src in [mp1, mp2] + mp3:
    for m in (src.get('mappings') or []):
        if isinstance(m, dict) and m.get('nomDansRecette') and m.get('idIngredient'):
            mappings[norm(m['nomDansRecette'])] = m['idIngredient']
mappings = {k: v for k, v in mappings.items() if v in ings}
print('mappings :', len(mappings), '| nouveaux ingrédients synthèse :',
      sum(len(m.get('nouveauxIngredients') or []) for m in [mp1, mp2] + mp3))

# ---------- 4. recettes v1 + v2 ----------
gras_exist = (load('gras-existants.json', required=False) or {}).get('gras') or {}
recettes, seen = [], set()
unresolved = {}


def clean_recette(r, default_gras):
    if not isinstance(r, dict) or not r.get('id') or not r.get('nom'):
        return None
    rid = str(r['id'])
    t = TYPES.get(norm(r.get('type')), None)
    if not t:
        problems.append('type inconnu "%s" sur %s -> vege' % (r.get('type'), rid))
        t = 'vege'
    ingl = []
    for i in (r.get('ingredients') or []):
        if not isinstance(i, dict) or not i.get('nom'):
            continue
        iid = i.get('idIngredient')
        if iid and iid not in ings:
            iid = None
        if not iid:
            iid = mappings.get(norm(i['nom'])) or nom2id.get(norm(i['nom']))
        if not iid:
            unresolved[i['nom']] = unresolved.get(i['nom'], 0) + 1
        try:
            q = float(i.get('quantite') or 0)
        except (TypeError, ValueError):
            q = 0
            problems.append('quantité non numérique sur %s / %s' % (rid, i['nom']))
        u = str(i.get('unite') or 'pièce')
        if u not in UNITES:
            problems.append('unité inconnue "%s" sur %s (gardée)' % (u, rid))
        ingl.append({'idIngredient': iid, 'nom': str(i['nom']), 'quantite': q,
                     'unite': u, 'optionnel': bool(i.get('optionnel')),
                     'note': (str(i['note']) if i.get('note') else None)})
    try:
        gr = int(r.get('gras') or default_gras.get(rid) or 2)
    except (TypeError, ValueError):
        gr = 2
    gr = min(3, max(1, gr))
    return {
        'id': rid, 'nom': str(r['nom']), 'type': t, 'gras': gr,
        'terroir': (str(r['terroir']) if r.get('terroir') else None),
        'description': str(r.get('description') or ''),
        'tempsTotalMin': int(r.get('tempsTotalMin') or 30),
        'portions': int(r.get('portions') or 4),
        'saisonMois': clean_months(r.get('saisonMois')),
        'ingredients': ingl,
        'etapes': [str(e) for e in (r.get('etapes') or [])],
        'astuceOptions': (str(r['astuceOptions']) if r.get('astuceOptions') else None),
        'tags': [str(x) for x in (r.get('tags') or [])],
    }


LOTS = [('recettes-%s.json', ('sudouest', 'quotidien', 'complets')),
        ('recettes2-%s.json', ('gourmand', 'classiques', 'sud', 'rapides', 'saisons')),
        ('recettes3-%s.json', LOTS3)]
for pattern, keys in LOTS:
    for lot in keys:
        data = load(pattern % lot, required=(pattern.startswith('recettes-')))
        if not data:
            continue
        for r in (data.get('recettes') or []):
            c = clean_recette(r, gras_exist)
            if not c:
                continue
            if c['id'] in seen:
                problems.append('recette en double ignorée : ' + c['id'])
                continue
            seen.add(c['id'])
            recettes.append(c)
print('recettes :', len(recettes))
if unresolved:
    print('ingrédients de recette sans référentiel (affichés tels quels) :')
    for k, v in sorted(unresolved.items(), key=lambda x: -x[1]):
        print('   %dx %s' % (v, k))

# ---------- 4b. décisions éditoriales (issues de la synthèse des agents) ----------
# produits de garde : récoltés sur quelques mois mais disponibles toute l'année -> jamais filtrés par la saison
GARDE = {'ail-rose-lautrec', 'ail-violet-cadours', 'noix', 'noisette', 'pignons', 'amandes'}
SAISON_OVERRIDE = {'potimarron': [1, 2, 9, 10, 11, 12], 'poire': [1, 2, 3, 8, 9, 10, 11, 12],
                   'navet': [1, 2, 3, 4, 5, 6, 10, 11, 12],        # navets nouveaux au printemps
                   'raisin-chasselas': [9, 10, 11]}                # chasselas de Moissac vendu jusqu'en novembre
PROVENANCE_OVERRIDE = {'thym': 'Provence (aire IGP)'}
for g in ings.values():
    g['garde'] = g['id'] in GARDE
    if g['id'] in SAISON_OVERRIDE:
        g['saisonMois'] = SAISON_OVERRIDE[g['id']]
    if g['id'] in PROVENANCE_OVERRIDE:
        g['provenanceLocale'] = PROVENANCE_OVERRIDE[g['id']]

DROP_RECETTES = ('brandade-cabillaud-nimoise', 'tian-provencal-courgettes-aubergines-tomates')
GRAS_OVERRIDE = {'burger-maison-cantal': 3, 'croque-monsieur-bechamel': 3, 'mounjetado-ariegeoise': 3}
TEMPS_OVERRIDE = {'poelee-dinde-curry': 40}
# (préfixe d'id de recette, fragment du nom d'ingrédient normalisé, action)
ING_FIX = [
    ('tielle-setoise', 'eau', 'drop'),
    ('salade-landaise', 'mais', {'idIngredient': 'mais-doux-conserve', 'nom': 'Maïs doux en conserve'}),
    ('salade-landaise', 'tomate', {'optionnel': True}),
    ('', 'graisse de canard', {'optionnel': True}),
    ('estouffade-boeuf', 'orange', {'optionnel': True}),
    ('crevettes-ail-violet', 'riz basmati', {'idIngredient': 'riz-camargue', 'nom': 'Riz de Camargue'}),
    ('saute-poulet-asperges', 'riz basmati', {'idIngredient': 'riz-camargue', 'nom': 'Riz de Camargue'}),
    ('gratin-poireaux-pommes-de-terre-laguiole', 'mache', {'optionnel': True}),
    ('sardines-grillees', 'oignon doux', {'idIngredient': 'oignon-jaune', 'nom': 'Oignon jaune'}),
    ('pot-au-feu', 'celeri branche', {'optionnel': True}),
    ('soupe-express', 'celeri', {'optionnel': True}),
    ('grand-aioli', 'haricot vert', {'optionnel': True}),
    ('tartines-gratinees-potimarron', 'roquette', {'optionnel': True}),
    ('tourin-ail', 'bouillon', {'quantite': 2.0, 'unite': 'pièce'}),
    ('burger-maison', 'salade verte', {'quantite': 1.0, 'unite': 'pièce'}),
]


def rid_match(rid, prefix):
    return prefix == '' or rid == prefix or rid.startswith(prefix)


recettes = [r for r in recettes if not any(rid_match(r['id'], p) for p in DROP_RECETTES)]
applied = {}
for r in recettes:
    for p, v in GRAS_OVERRIDE.items():
        if rid_match(r['id'], p):
            r['gras'] = v
            applied['gras:' + p] = applied.get('gras:' + p, 0) + 1
    for p, v in TEMPS_OVERRIDE.items():
        if rid_match(r['id'], p):
            r['tempsTotalMin'] = v
            applied['temps:' + p] = applied.get('temps:' + p, 0) + 1
    kept = []
    for i in r['ingredients']:
        drop = False
        for p, frag, action in ING_FIX:
            if rid_match(r['id'], p) and frag in norm(i['nom']):
                key = 'ing:%s/%s' % (p or '*', frag)
                applied[key] = applied.get(key, 0) + 1
                if action == 'drop':
                    drop = True
                else:
                    i.update(action)
        if not drop:
            kept.append(i)
    r['ingredients'] = kept
print('recettes après suppression des doublons :', len(recettes))
print('correctifs appliqués :', applied)
for p, frag, _ in ING_FIX:
    if not any(k == 'ing:%s/%s' % (p or '*', frag) for k in applied):
        problems.append('correctif sans effet : %s / %s' % (p or '*', frag))
for p in list(GRAS_OVERRIDE) + list(TEMPS_OVERRIDE):
    if not any(k.endswith(':' + p) for k in applied):
        problems.append('correctif sans effet : ' + p)

# ---------- 4c. photos (data/images/<id>.json + fichiers app/img/) ----------
IMGDIR = os.path.join(D, 'images')
nimg = 0
for r in recettes:
    r['image'] = None
    pj = os.path.join(IMGDIR, r['id'] + '.json')
    if not os.path.exists(pj):
        continue
    try:
        with open(pj, encoding='utf-8-sig') as f:
            m = json.load(f)
        if os.path.exists(os.path.join(BASE, 'app', 'img', m.get('fichier') or '')):
            r['image'] = {'fichier': m['fichier'], 'auteur': m.get('auteur') or '', 'licence': m.get('licence') or '',
                          'licenceUrl': m.get('licenceUrl') or '', 'page': m.get('page') or '',
                          'illustrative': m.get('qualite') == 'proche'}
            nimg += 1
        else:
            problems.append('photo absente sur disque : ' + r['id'])
    except Exception as e:
        problems.append('métadonnées photo invalides %s : %s' % (r['id'], e))
print('recettes avec photo :', nimg, '/', len(recettes))

# ---------- 5. drive + sortie ----------
drive = load('drive.json', required=False) or {}

out = {
    'meta': {'genereLe': '2026-10-16', 'version': 2,
             'zones': {'occitanie': ['Occitanie'],
                       'sud': ['Nouvelle-Aquitaine', 'Occitanie', "Provence-Alpes-Côte d'Azur", 'Auvergne-Rhône-Alpes'],
                       'france': REGIONS}},
    'ingredients': sorted(ings.values(), key=lambda g: (g['rayon'], norm(g['nom']))),
    'recettes': recettes,
    'drive': drive,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
print('écrit :', OUT, '(%d Ko)' % (os.path.getsize(OUT) // 1024))

# ---------- stats ----------
cats = {}
for g in ings.values():
    cats[g['categorie']] = cats.get(g['categorie'], 0) + 1
print('catégories :', cats)
grs = {}
for r in recettes:
    grs[r['gras']] = grs.get(r['gras'], 0) + 1
print('niveaux de gras :', grs)
sud = set(out['meta']['zones']['sud'])
nsud = sum(1 for g in ings.values() if set(g['regions']) & sud)
nocc = sum(1 for g in ings.values() if 'Occitanie' in g['regions'])
print('ingrédients avec production Sud :', nsud, '| Occitanie :', nocc, '| sans région :',
      sum(1 for g in ings.values() if not g['regions']))

if problems:
    print('\nPROBLÈMES (%d) :' % len(problems))
    for p in problems[:60]:
        print(' -', p)
else:
    print('\naucun problème détecté')
