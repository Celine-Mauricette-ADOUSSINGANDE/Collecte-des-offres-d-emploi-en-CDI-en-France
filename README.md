# 🎯 Job Tracker — Data Science CDI France

Scraper automatique qui surveille **6 intitulés** de postes Data Science
en CDI en France, toutes les 6h, sur 4 sources simultanées.

## Architecture

```
GitHub Actions (cron 6h)
    └── scraper/main.py
            ├── France Travail API  ─┐
            ├── Indeed RSS           ├── → storage.py → Supabase (PostgreSQL)
            ├── Welcome to the Jungle RSS │
            └── APEC                ─┘
                                          └── alerts.py → SendGrid (email)

Vercel (frontend statique)
    └── frontend/index.html ←── Supabase JS (temps réel)
```

---

## 🚀 Déploiement — étape par étape

### 1. Supabase — Base de données

1. Créer un compte sur [supabase.com](https://supabase.com) (gratuit)
2. Créer un nouveau projet
3. Aller dans **SQL Editor** et exécuter ce SQL :

```sql
CREATE TABLE IF NOT EXISTS jobs (
  id           TEXT PRIMARY KEY,
  title        TEXT NOT NULL,
  company      TEXT,
  location     TEXT,
  contract     TEXT,
  source       TEXT,
  url          TEXT,
  published_at TIMESTAMPTZ,
  description  TEXT,
  salary       TEXT,
  search_label TEXT,
  status       TEXT DEFAULT 'new',
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS jobs_created_at_idx ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS jobs_status_idx     ON jobs(status);
CREATE INDEX IF NOT EXISTS jobs_source_idx     ON jobs(source);
```

4. Récupérer dans **Settings > API** :
   - `SUPABASE_URL`
   - `SUPABASE_KEY` (clé `anon`)

---

### 2. France Travail API

1. S'inscrire sur [francetravail.io](https://francetravail.io/data/api)
2. Créer une application → cocher `Offres d'emploi v2`
3. Récupérer `Client ID` et `Client Secret`

---

### 3. SendGrid — Alertes email

1. Créer un compte sur [sendgrid.com](https://sendgrid.com) (100 emails/jour gratuits)
2. Créer une clé API avec permission `Mail Send`
3. Vérifier ton adresse expéditrice (Sender Authentication)

---

### 4. GitHub — Secrets

Dans ton repo GitHub : **Settings > Secrets and variables > Actions > New repository secret**

Ajouter ces 7 secrets :

| Nom               | Valeur                        |
|-------------------|-------------------------------|
| SUPABASE_URL      | https://xxxx.supabase.co      |
| SUPABASE_KEY      | clé anon Supabase             |
| FT_CLIENT_ID      | Client ID France Travail      |
| FT_CLIENT_SECRET  | Client Secret France Travail  |
| SENDGRID_API_KEY  | SG.xxxxxxxxx                  |
| ALERT_EMAIL_FROM  | ton.adresse@gmail.com         |
| ALERT_EMAIL_TO    | ton.adresse@gmail.com         |

---

### 5. Vercel — Dashboard

1. Aller sur [vercel.com](https://vercel.com) > **Import Git Repository**
2. Importer ton repo GitHub
3. Dans `frontend/index.html`, remplacer :
   ```js
   const SUPABASE_URL = "https://XXXX.supabase.co";
   const SUPABASE_KEY = "YOUR_ANON_KEY";
   ```
   par tes vraies valeurs Supabase
4. Deploy → ton dashboard est en ligne !

---

### 6. Premier lancement manuel

Dans GitHub **Actions > 🔍 Job Scraper > Run workflow**
pour tester immédiatement sans attendre le cron.

---

## 📁 Structure du projet

```
job-tracker/
├── .github/
│   └── workflows/
│       └── scraper.yml        # Cron GitHub Actions
├── scraper/
│   ├── __init__.py
│   ├── config.py              # Intitulés & paramètres
│   ├── main.py                # Orchestrateur
│   ├── storage.py             # Déduplication + Supabase
│   ├── alerts.py              # Email SendGrid
│   └── sources/
│       ├── __init__.py
│       ├── france_travail.py  # API officielle
│       ├── rss_feeds.py       # Indeed + WTTJ
│       └── apec.py            # APEC
├── frontend/
│   └── index.html             # Dashboard Vercel
├── vercel.json
├── requirements.txt
├── .env.example
└── README.md
```

## ✏️ Personnalisation

- **Ajouter un intitulé** : modifier `SEARCH_QUERIES` dans `config.py`
- **Changer la fréquence** : modifier le cron dans `scraper.yml` (`0 */4 * * *` = toutes les 4h)
- **Désactiver une source** : retirer son nom de la liste `SOURCES` dans `config.py`
