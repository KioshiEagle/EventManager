# EventManager — Agenda Unifié Lorraine

Application [Streamlit](https://streamlit.io/) qui agrège les événements de plusieurs
agendas de Nancy / Lorraine (université, entrepreneuriat, culture, tech) dans une
seule interface de tri. On scanne les sources, on parcourt les cartes d'événements,
on garde ou on jette, et on exporte vers Google Agenda en un clic.

## Fonctionnalités

- **Scraping multi-sources** — un scraper dédié par site, lancé individuellement ou
  tous en même temps via « Scanner Tout ».
- **Déduplication** — chaque événement a un `id` (hash MD5 de son URL ou de sa
  date + titre) ; un événement déjà connu n'est jamais réimporté.
- **Tri manuel** — deux onglets : « À Trier » et « Poubelle ». Chaque carte a un
  bouton *Passer* / *Restaurer*.
- **Nettoyage automatique** — au démarrage, les événements dont la date est passée
  de plus de 7 jours sont supprimés de la base.
- **Normalisation des dates** — formats hétérogènes (français `14h30`, anglais
  `am/pm`, ISO, fuseaux Meetup) ramenés à `JJ/MM/AAAA | HHhMM - HHhMM`.
- **Export Google Agenda** — lien `TEMPLATE` pré-rempli (titre, dates, lieu, URL)
  généré par carte quand la date est connue.
- **Filtres** — sélection des sources actives (persistée dans `config.json`) et
  filtre par source dans l'onglet de tri.

## Sources supportées

| Source   | Site                                              | Type              |
|----------|---------------------------------------------------|-------------------|
| Factuel  | factuel.univ-lorraine.fr/agenda                   | Université (10 pages) |
| Pépite   | pepite-peel.pepitizy.fr                           | Entrepreneuriat étudiant (5 pages) |
| Sciences | conferences-sciences-et-societe.univ-lorraine.fr  | Conférences       |
| Meetup   | meetup.com (recherche Nancy, 10 miles)            | Meetups           |
| ALS      | als.univ-lorraine.fr                              | Académie Lorraine des Sciences |
| Museum   | museumaquariumdenancy.eu                          | Expo / conférences (ateliers exclus) |
| MEDEF    | medef-meurthe-moselle.fr                          | Entrepreneuriat   |
| LORIA    | loria.fr/events                                   | Recherche (The Events Calendar) |
| ENACT    | cluster-ia-enact.ai/events                        | Innovation IA (The Events Calendar) |

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run eventmanager.py
```

L'application s'ouvre dans le navigateur. Cliquer sur **🌍 Scanner Tout** (ou
**Scanner <source>**) pour récupérer les événements, puis trier dans l'onglet
**À Trier**.

## Fichiers de données

| Fichier          | Rôle                                                        |
|------------------|------------------------------------------------------------|
| `eventdata.json` | Base des événements (créée / mise à jour automatiquement).  |
| `config.json`    | Sources actives retenues pour « Scanner Tout ». Optionnel.  |

Les deux sont générés au runtime ; ne pas les versionner si l'on veut repartir
d'une base vierge.

## Structure du code

`eventmanager.py` est organisé en sections :

1. **Configuration & style** — `st.set_page_config`, CSS des cartes, couleurs par type.
2. **Fonctions utilitaires** — chargement / sauvegarde JSON, nettoyage HTML,
   parsing et normalisation des dates.
3. **Scrapers** — une fonction `fetch_*` par source + un routeur `scan_source`.
4. **Rendu** — `render_card` produit le HTML d'une carte événement.
5. **App principale** — titre, contrôles de scan, onglets de tri.

Les erreurs de scraping sont collectées dans `SCRAPE_ERRORS` et affichées après
chaque scan sans interrompre les autres sources.

## Limites connues

- Les scrapers dépendent du HTML des sites cibles : un changement de structure
  côté source casse le scraper concerné (les autres continuent de fonctionner).
- Meetup : les horaires renvoyés par l'API sont traités comme de l'UTC puis
  convertis en `Europe/Paris` (contournement d'une incohérence de fuseau).
- Pas de tests automatisés à ce stade.
</content>
</invoke>
