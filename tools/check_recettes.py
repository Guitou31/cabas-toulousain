"""Contrôle mécanique des lots de recettes v3 (data/recettes3-*.json) avant assemblage :
ids, schéma, unités, ingrédients résolus, quantités, étapes, doublons de noms avec l'existant et entre lots."""
import glob, json, os, re, sys, unicodedata

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(BASE, 'data')
LOTS3 = ('printemps-ete', 'monde', 'poisson-mer', 'viandes-volailles', 'vege-legumes', 'rapides-famille')
UNITES = {'g', 'kg', 'ml', 'cl', 'l', 'pièce', 'c. à soupe', 'c. à café', 'gousse', 'botte', 'tranche', 'boîte', 'pincée', 'sachet'}
RAYONS = {'Fruits & Légumes', 'Boucherie & Volaille', 'Poissonnerie', 'Crèmerie & Fromages', 'Épicerie', 'Épices & Condiments', 'Boulangerie'}
CATS = {'fruit', 'legume', 'viande', 'poisson', 'cremerie', 'feculent', 'epicerie', 'condiment'}
REGIONS = {'Auvergne-Rhône-Alpes', 'Bourgogne-Franche-Comté', 'Bretagne', 'Centre-Val de Loire', 'Corse', 'Grand Est',
           'Hauts-de-France', 'Île-de-France', 'Normandie', 'Nouvelle-Aquitaine', 'Occitanie', 'Pays de la Loire',
           "Provence-Alpes-Côte d'Azur"}
LABELS = {'AOP', 'IGP', 'Label Rouge', 'STG', 'AB', 'Origine France Garantie'}
TYPES = {'viande', 'volaille', 'poisson', 'vege'}


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def est_v3(rid):
    return any(rid.endswith('-' + k) for k in LOTS3)


app = json.load(open(os.path.join(BASE, 'app', 'data.json'), encoding='utf-8'))
ids_exist = {g['id'] for g in app['ingredients']}
noms_exist = {norm(r['nom']): r['id'] for r in app['recettes'] if not est_v3(r['id'])}
ids_recettes_exist = {r['id'] for r in app['recettes']}

errs, warns = [], []
seen_ids, seen_noms, new_ings = {}, {}, {}
total = 0
for path in sorted(glob.glob(os.path.join(D, 'recettes3-*.json'))):
    lot = os.path.basename(path)[len('recettes3-'):-5]
    try:
        d = json.load(open(path, encoding='utf-8-sig'))
    except Exception as e:
        errs.append('%s : JSON invalide : %s' % (lot, e))
        continue
    for g in d.get('nouveauxIngredients') or []:
        gid = g.get('id')
        if not gid or not g.get('nom'):
            errs.append('%s : nouvel ingrédient sans id/nom' % lot)
            continue
        if gid in ids_exist:
            warns.append('%s : nouvel ingrédient %s existe déjà dans le référentiel (ignoré par build)' % (lot, gid))
        if gid in new_ings and new_ings[gid] != lot:
            warns.append('%s : nouvel ingrédient %s aussi défini dans %s (première définition gardée)' % (lot, gid, new_ings[gid]))
        new_ings.setdefault(gid, lot)
        if g.get('rayon') not in RAYONS:
            errs.append('%s/%s : rayon inconnu %r' % (lot, gid, g.get('rayon')))
        if g.get('categorie') not in CATS:
            errs.append('%s/%s : catégorie inconnue %r' % (lot, gid, g.get('categorie')))
        for r in g.get('regions') or []:
            if r not in REGIONS:
                errs.append('%s/%s : région inconnue %r' % (lot, gid, r))
        for l in g.get('siqo') or []:
            if l.get('label') not in LABELS:
                errs.append('%s/%s : label inconnu %r' % (lot, gid, l.get('label')))
        if g.get('categorie') in ('fruit', 'legume') and not g.get('saisonMois'):
            warns.append('%s/%s : fruit/légume sans saisonMois' % (lot, gid))
    lot_ids = ids_exist | set(new_ings)
    for r in d.get('recettes') or []:
        total += 1
        rid = r.get('id', '?')
        ctx = '%s/%s' % (lot, rid)
        if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', rid) or not rid.endswith('-' + lot):
            errs.append(ctx + ' : id invalide ou sans suffixe -' + lot)
        if rid in seen_ids:
            errs.append(ctx + ' : id en double avec ' + seen_ids[rid])
        seen_ids.setdefault(rid, lot)
        n = norm(r.get('nom'))
        if n in noms_exist:
            errs.append(ctx + ' : même nom qu une recette existante ' + noms_exist[n])
        if n in seen_noms:
            errs.append(ctx + ' : même nom que ' + seen_noms[n])
        seen_noms.setdefault(n, ctx)
        if r.get('type') not in TYPES:
            errs.append(ctx + ' : type %r' % r.get('type'))
        if r.get('gras') not in (1, 2, 3):
            errs.append(ctx + ' : gras %r' % r.get('gras'))
        if r.get('portions') != 4:
            warns.append(ctx + ' : portions %r' % r.get('portions'))
        if not isinstance(r.get('tempsTotalMin'), int) or not 5 <= r['tempsTotalMin'] <= 300:
            errs.append(ctx + ' : tempsTotalMin %r' % r.get('tempsTotalMin'))
        desc = r.get('description') or ''
        if not 60 <= len(desc) <= 200:
            warns.append(ctx + ' : description de %d caractères' % len(desc))
        for m in r.get('saisonMois') or []:
            if not isinstance(m, int) or not 1 <= m <= 12:
                errs.append(ctx + ' : mois %r' % m)
        et = r.get('etapes') or []
        if not 3 <= len(et) <= 10:
            warns.append(ctx + ' : %d étapes' % len(et))
        ingl = r.get('ingredients') or []
        if len(ingl) < 3:
            errs.append(ctx + ' : %d ingrédients' % len(ingl))
        vus = set()
        for i in ingl:
            iid = i.get('idIngredient')
            if iid is not None and iid not in lot_ids:
                errs.append(ctx + ' : idIngredient inconnu %r (%s)' % (iid, i.get('nom')))
            if iid is None:
                warns.append(ctx + ' : ingrédient sans id : %s' % i.get('nom'))
            if i.get('unite') not in UNITES:
                errs.append(ctx + ' : unité %r sur %s' % (i.get('unite'), i.get('nom')))
            try:
                if float(i.get('quantite')) <= 0:
                    errs.append(ctx + ' : quantité nulle sur %s' % i.get('nom'))
            except (TypeError, ValueError):
                errs.append(ctx + ' : quantité non numérique sur %s' % i.get('nom'))
            if iid and iid in vus:
                warns.append(ctx + ' : ingrédient %s listé deux fois' % iid)
            vus.add(iid)
        if not r.get('astuceOptions'):
            warns.append(ctx + ' : pas d astuceOptions')
        if not r.get('tags'):
            warns.append(ctx + ' : pas de tags')
        if any(t != t.lower() for t in r.get('tags') or []):
            warns.append(ctx + ' : tag avec majuscule')
    print('%-18s %3d recettes, %2d nouveaux ingrédients' % (lot, len(d.get('recettes') or []), len(d.get('nouveauxIngredients') or [])))
print('total :', total, 'recettes v3 |', len(new_ings), 'nouveaux ingrédients')
if warns:
    print('\nAVERTISSEMENTS (%d) :' % len(warns))
    for w in warns:
        print(' -', w)
if errs:
    print('\nERREURS (%d) :' % len(errs))
    for e in errs:
        print(' -', e)
    sys.exit(1)
print('\naucune erreur bloquante')
