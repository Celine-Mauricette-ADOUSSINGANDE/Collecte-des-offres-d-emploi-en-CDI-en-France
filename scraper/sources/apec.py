# ═══════════════════════════════════════════════════════
#  sources/apec.py
#  APEC — API interne (non documentée mais stable)
#  Aucune clé requise, scraping direct JSON
# ═══════════════════════════════════════════════════════

import requests
from datetime import datetime, timezone
from scraper.config import APEC_SEARCH_URL

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-tracker-bot/1.0)",
    "Accept":     "application/json",
    "Referer":    "https://www.apec.fr/",
}


def _parse_offer(raw: dict, query_label: str) -> dict:
    """Normaliser une offre APEC."""
    salary_min = raw.get("salaireMin", "")
    salary_max = raw.get("salaireMax", "")
    salary = f"{salary_min}–{salary_max} k€/an" if salary_min and salary_max else ""

    return {
        "title":        raw.get("intitule", ""),
        "company":      raw.get("nomEntreprise", "Non précisé"),
        "location":     raw.get("lieuDeTravail", "France"),
        "contract":     "CDI",
        "source":       "APEC",
        "url":          f"https://www.apec.fr/candidat/recherche-emploi.html/emploi/{raw.get('numeroOffre', '')}",
        "published_at": raw.get("datePublication", datetime.now(timezone.utc).isoformat()),
        "description":  raw.get("accroche", "")[:500],
        "salary":       salary,
        "search_label": query_label,
    }


def fetch(query: str, query_label: str) -> list[dict]:
    """Chercher les offres CDI sur APEC pour un intitulé."""
    offers = []
    try:
        payload = {
            "motsCles":       query,
            "typeContrat":    ["CDI"],
            "lieux":          [],          # Toute la France
            "nbResultatsParPage": 50,
            "debut":          0,
            "tri":            0,           # Tri par date
        }
        resp = requests.post(APEC_SEARCH_URL, json=payload, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for raw in data.get("resultats", []):
            offers.append(_parse_offer(raw, query_label))

        print(f"[APEC] '{query}' → {len(offers)} offres")

    except Exception as e:
        print(f"[APEC] Erreur pour '{query}': {e}")

    return offers
