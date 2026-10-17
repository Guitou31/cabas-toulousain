# Le Cabas Toulousain

Planification des repas de la semaine et liste de courses, en privilégiant les produits du grand Sud
(Nouvelle-Aquitaine, Occitanie, Provence-Alpes-Côte d'Azur, Auvergne-Rhône-Alpes), les fruits et légumes
de saison et les pâtes et riz complets.

## Contenu du dépôt

- `docs/` — le site installable (PWA) publié par GitHub Pages : `index.html`, `data.json`, `manifest.webmanifest`,
  `sw.js` (fonctionnement hors ligne), `icons/`. **Ne pas modifier à la main : généré.**
- `app/index.html` — la source de la page, commune à la version GitHub Pages et à l'artifact claude.ai.
- `app/data.json` — la base assemblée (ingrédients avec régions de production, labels SIQO, saisons ; recettes).
- `data/` — les sorties brutes des agents (ingrédients, recettes, vérifications, mappings, drives).
- `tools/build_data.py` — assemble `app/data.json` depuis `data/` (corrections, mappings, décisions éditoriales).
- `tools/build_pwa.py` — génère `docs/` depuis `app/` (document complet, manifeste, service worker, icônes).
- `tools/check_js.py` — contrôle d'équilibrage des délimiteurs du script embarqué.

## Régénérer

```bash
python -X utf8 -I tools/build_data.py
python -X utf8 -I tools/build_pwa.py
```

Le fichier optionnel `pwa.config.json` (`{"url": "https://<compte>.github.io/<depot>/"}`) renseigne l'adresse
de la version installable, utilisée par l'artifact claude.ai pour afficher un QR de transfert.

## Données

Labels contrôlés via les registres officiels (INAO), régions de production et saisons vérifiées par recherche
documentaire (Agreste, FranceAgriMer, interprofessions). L'origine réelle se vérifie toujours sur l'étiquette.
