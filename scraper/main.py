# ═══════════════════════════════════════════════════════
#  main.py — Orchestrateur principal
#  Lancé par GitHub Actions toutes les 6h
# ═══════════════════════════════════════════════════════

import os
import sys
from dotenv import load_dotenv

# Charger les variables .env en local (ignoré en CI, les secrets viennent de GitHub)
load_dotenv()

from scraper.config import SEARCH_QUERIES, SOURCES
from scraper.sources import france_travail, rss_feeds, apec
from scraper.storage import deduplicate, save_new_offers, get_stats
from scraper.alerts import send_alert


def run_scraper() -> list[dict]:
    """Lancer le scraping sur toutes les sources et tous les intitulés."""
    all_offers = []

    for label, queries in SEARCH_QUERIES.items():
        print(f"\n── Recherche : {label} ──")
        for query in queries:

            # France Travail (API officielle)
            if "france_travail" in SOURCES:
                all_offers += france_travail.fetch(query, label)

            # Indeed RSS
            if "indeed_rss" in SOURCES:
                all_offers += rss_feeds.fetch_indeed(query, label)

            # Welcome to the Jungle RSS
            if "welcome_rss" in SOURCES:
                all_offers += rss_feeds.fetch_wttj(query, label)

            # APEC
            if "apec" in SOURCES:
                all_offers += apec.fetch(query, label)

    print(f"\n── Total brut collecté : {len(all_offers)} offres ──")
    return all_offers


def main():
    print("═" * 50)
    print("  JOB TRACKER — Data Science CDI France")
    print("═" * 50)

    # 1. Scraping
    raw_offers = run_scraper()

    # 2. Déduplication (doublons dans le lot courant)
    unique_offers = deduplicate(raw_offers)
    print(f"\n── Après déduplication : {len(unique_offers)} offres uniques ──")

    # 3. Sauvegarde (ignore les offres déjà en base)
    new_offers = save_new_offers(unique_offers)

    # 4. Stats globales
    stats = get_stats()
    print(f"\n── Stats base : {stats['total']} offres au total ──")

    # 5. Alerte email (uniquement si nouvelles offres)
    if new_offers:
        send_alert(new_offers, stats)
    else:
        print("[Email] Pas de nouveauté, email non envoyé.")

    print("\n✅ Scraping terminé avec succès.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
