# 🎯 Job Tracker — Data Scientist ou Data Analyst CDI France

Scraper automatique qui surveille les postes de Data Scientist ou Data Analyst
en CDI en France, toutes les 6h, sur 2 sources simultanées (France Travaile et Hello work).




## 🚀 Déploiement — étape par étape

1. Supabase — Base de données

2. France Travail API

3. SendGrid — Alertes email

4. GitHub — Secrets

5. Vercel — Dashboard

6. Premier lancement manuel



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
│       ├── hellowork.py       # scraping
│                 
├── frontend/
│   └── index.html             # Dashboard Vercel
├── vercel.json
├── requirements.txt
├── .env.example
└── README.md
```
