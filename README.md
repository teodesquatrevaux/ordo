# Ordo, POC v1 (18 novembre)

Lit une commande reçue par email (PDF, Excel, corps de mail, scan), retrouve chaque article dans le catalogue,
signale ce qui doit être vérifié, puis produit un fichier d'import ERP et un brouillon d'accusé de réception.

## Lancer en local
```bash
pip install -r requirements.txt
cp .env.example .env          # puis colle ta clé OpenRouter dans .env (jamais dans le code, jamais sur GitHub)
streamlit run app.py
```
Sans clé, l'application tourne en mode hors-ligne (règles simples) : pratique pour une démo sans réseau.

## Mettre en ligne (lien partageable, Streamlit Community Cloud)
1. Pousse ce dossier sur un dépôt GitHub (le `.gitignore` exclut déjà `.env`).
2. Sur share.streamlit.io : New app, choisis le dépôt, fichier principal `app.py`.
3. Dans Advanced settings > Secrets, colle :
   ```
   OPENROUTER_API_KEY = "ta-cle"
   ORDO_MODEL = "anthropic/claude-haiku-5.5"
   ```
Attention : un dépôt public expose le code (pas la clé si elle est dans les Secrets).

## Évaluer
```bash
python eval.py offline   # règles, sans IA
python eval.py llm       # IA, environ 10 appels
```
Le mode hors-ligne a été écrit en regardant ces 10 cas : son score n'est pas une preuve.
Le chiffre à présenter est celui du mode IA, puis celui sur de vraies commandes FEKU.

## Architecture
| Fichier | Rôle |
|---|---|
| `ordo/ingest.py` | lit .eml, PDF (texte ou scan), Excel, image |
| `ordo/extract_llm.py` | lecture par IA (OpenRouter, sortie JSON imposée). L'IA recopie les références, elle ne les choisit pas |
| `ordo/extract_rules.py` | lecture hors-ligne (secours) |
| `ordo/match.py` | réf. exacte, alias appris par client, fautes de frappe, recherche par désignation, refus si ambigu |
| `ordo/pipeline.py` | enchaîne tout, applique les modifications demandées dans l'email |
| `ordo/export.py` | CSV d'import ERP (format générique : format Simax à confirmer) |
| `ordo/ar.py` | accusé de réception PDF + email |
| `app.py` | interface Streamlit |
| `eval.py` | score sur les 10 cas de `demo/` |

## Limites connues
- Catalogue de démo : 49 références vérifiées, pas le catalogue complet.
- Format d'import Simax inconnu, règle de conditionnement FEKU inconnue (lignes signalées, jamais tranchées).
- Les alias appris sont stockés dans `data/aliases.json` : sur Streamlit Cloud ce fichier est remis à zéro à chaque redémarrage.
- Données de démo synthétiques.
