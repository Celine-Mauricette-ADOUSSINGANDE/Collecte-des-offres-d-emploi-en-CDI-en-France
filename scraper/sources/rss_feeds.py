# ═══════════════════════════════════════════════════════
#  sources/rss_feeds.py
#  Scraping via flux RSS — Indeed & Welcome to the Jungle
#  Aucune clé API requise
# ═══════════════════════════════════════════════════════

import feedparser
from urllib.parse import quote_plus
from datetime import datetime, timezone
from scraper.config import INDEED_RSS_BASE, WTTJ_RSS_BASE


def _parse_date(entry) -> str:
    """Extraire la date de publication d'une entrée RSS."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def _fetch_rss(url: str, source_name: str, query_label: str) -> list[dict]:
    """Parser un flux RSS et normaliser les entrées."""
    offers = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title    = getattr(entry, "title", "")
            link     = getattr(entry, "link", "")
            summary  = getattr(entry, "summary", "")[:500]
            location = ""

            # Indeed encode l'entreprise et la localisation dans le titre
            # Format typique : "Intitulé - Entreprise - Ville"
            parts = title.split(" - ")
            company  = parts[1].strip() if len(parts) >= 2 else "Non précisé"
            location = parts[2].strip() if len(parts) >= 3 else "France"

            offers.append({
                "title":        parts[0].strip() if parts else title,
                "company":      company,
                "location":     location,
                "contract":     "CDI",
                "source":       source_name,
                "url":          link,
                "published_at": _parse_date(entry),
                "description":  summary,
                "salary":       "",
                "search_label": query_label,
            })

        print(f"[{source_name}] '{query_label}' → {len(offers)} offres")

    except Exception as e:
        print(f"[{source_name}] Erreur pour '{query_label}': {e}")

    return offers


def fetch_indeed(query: str, query_label: str) -> list[dict]:
    """Flux RSS Indeed France pour un intitulé."""
    url = INDEED_RSS_BASE.format(query=quote_plus(query + " CDI"))
    return _fetch_rss(url, "Indeed", query_label)


def fetch_wttj(query: str, query_label: str) -> list[dict]:
    """Flux RSS Welcome to the Jungle pour un intitulé."""
    url = WTTJ_RSS_BASE.format(query=quote_plus(query))
    return _fetch_rss(url, "Welcome to the Jungle", query_label)
