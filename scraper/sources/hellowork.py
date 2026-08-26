# ═══════════════════════════════════════════════════════
#  sources/hellowork.py
#  Scraper Hello Work — pages métier (pas de RSS)
#  Fonctionne depuis GitHub Actions car pas de blocage IP
#  sur les pages /emploi/metier_xxx.html
# ═══════════════════════════════════════════════════════

import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone

BASE_URL = "https://www.hellowork.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Pages métier Hello Work ──────────────────────────
# URL stables qui ne changent pas et ne sont pas bloquées
METIER_URLS = {
    "Data Scientist":       "https://www.hellowork.com/fr-fr/emploi/metier_data-scientist.html",
    "Data Analyst":         "https://www.hellowork.com/fr-fr/emploi/metier_data-analyst.html",
    "Business Analyst":     "https://www.hellowork.com/fr-fr/emploi/metier_business-analyst.html",
    "Data Scientist Junior":"https://www.hellowork.com/fr-fr/emploi/metier_data-scientist.html",
    "Quantitative Analyst": "https://www.hellowork.com/fr-fr/emploi/metier_data-analyst.html",
    "Consultant Data":      "https://www.hellowork.com/fr-fr/emploi/metier_data-scientist.html",
}

# ── Mots-clés pour valider le titre ─────────────────
TARGET_KEYWORDS = [
    "data analyst",
    "data scientist",
    "business analyst",
    "data analyst",
    "analyste données",
    "analyste quantitatif",
    "quantitative analyst",
    "consultant data",
    "consultant ia",
    "machine learning",
    "ml engineer",
]

# ── Mots-clés handicap à exclure ────────────────────
HANDICAP_KEYWORDS = [
    "handicap", "handicapé", "handicapés", "handi",
    "rqth", "travailleur handicapé", "travailleurs handicapés",
    "talents handicap", "forum handicap", "emploi handicap",
    "disability", "disabled", "agefiph", "fiphfp",
]


# ════════════════════════════════════════════════════════
#  Fonctions utilitaires
# ════════════════════════════════════════════════════════

def _normalize(text: str) -> str:
    """Mettre en minuscules et nettoyer les espaces."""
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _is_target_job(title: str) -> bool:
    """Vérifier si le titre correspond à nos intitulés."""
    t = _normalize(title)
    return any(kw in t for kw in TARGET_KEYWORDS)


def _is_cdi(text: str) -> bool:
    """Vérifier que l'offre est bien en CDI et pas en alternance."""
    t = _normalize(text)
    if "cdi" not in t:
        return False
    excluded = ["alternance", "apprentissage", "apprenti", "stage", "stagiaire"]
    return not any(w in t for w in excluded)


def _is_handicap(title: str, text: str) -> bool:
    """Vérifier si l'offre est destinée aux personnes handicapées."""
    combined = _normalize(title + " " + text)
    return any(kw in combined for kw in HANDICAP_KEYWORDS)


def _extract_location(container_text: str) -> str:
    """
    Essayer d'extraire la ville depuis le texte du conteneur.
    Hello Work inclut souvent la localisation dans le bloc.
    """
    # Chercher un code postal 5 chiffres
    cp = re.search(r'\b(\d{5})\b', container_text)
    if cp:
        # Essayer de trouver la ville à côté du code postal
        context = container_text[max(0, cp.start()-30):cp.end()+30]
        return context.strip()

    # Chercher des patterns de localisation communs
    patterns = [
        r'([A-Z][a-zéèêëàâùûüîïôç\-]+(?:\s[A-Z][a-zéèêëàâùûüîïôç\-]+)*)\s*\(\d{2}\)',
        r'(Paris|Lyon|Marseille|Toulouse|Bordeaux|Nantes|Lille|Strasbourg|Rennes|Montpellier)',
    ]
    for pat in patterns:
        m = re.search(pat, container_text)
        if m:
            return m.group(1).strip()

    return "France"


def _extract_salary(container_text: str) -> str:
    """Essayer d'extraire le salaire depuis le texte du conteneur."""
    patterns = [
        r'(\d+[\s]?[Kk]€?\s*[-–]\s*\d+[\s]?[Kk]€?)',
        r'(\d+\s*000\s*€?\s*[-–]\s*\d+\s*000\s*€?)',
        r'([\d\s]+€\s*/\s*an)',
    ]
    for pat in patterns:
        m = re.search(pat, container_text)
        if m:
            return m.group(1).strip()
    return ""


# ════════════════════════════════════════════════════════
#  Scraper principal
# ════════════════════════════════════════════════════════

def _scrape_page(url: str, label: str) -> list[dict]:
    """Scraper une page métier Hello Work et retourner les offres CDI."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [❌ Hello Work] '{label}' erreur requête : {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    offers  = []
    seen    = set()

    for link in soup.find_all("a", href=True):
        title = link.get_text(" ", strip=True)
        href  = link.get("href", "")

        if not title or not href:
            continue

        # Filtrer sur le titre
        if not _is_target_job(title):
            continue

        # URL complète de l'offre
        job_url = urljoin(BASE_URL, href)

        # Garder uniquement les pages d'offres Hello Work
        if "/fr-fr/emplois/" not in job_url:
            continue

        # Déduplication par URL
        if job_url in seen:
            continue
        seen.add(job_url)

        # Remonter dans le DOM pour récupérer le contexte complet
        container = link
        for _ in range(6):
            if container.parent:
                container = container.parent
        container_text = container.get_text(" ", strip=True)

        # CDI uniquement
        if not _is_cdi(container_text):
            continue

        # Exclure offres handicap
        if _is_handicap(title, container_text):
            continue

        location = _extract_location(container_text)
        salary   = _extract_salary(container_text)

        offers.append({
            "title":        title,
            "company":      "Non précisé",   # Non disponible sur la page liste
            "location":     location,
            "contract":     "CDI",
            "source":       "Hello Work",
            "url":          job_url,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "description":  container_text[:500],
            "salary":       salary,
            "search_label": label,
            "secteur":      "",
            "experience":   "",
        })

    return offers


# ════════════════════════════════════════════════════════
#  Point d'entrée appelé depuis main.py
# ════════════════════════════════════════════════════════

def fetch_all() -> list[dict]:
    """
    Scraper toutes les pages métier Hello Work.
    Appelé une seule fois depuis main.py (pas par requête).
    Retourne une liste d'offres normalisées.
    """
    all_offers  = []
    seen_urls   = set()           # Déduplication globale inter-catégories

    for label, url in METIER_URLS.items():
        print(f"\n  [Hello Work] Scraping '{label}'...")
        try:
            offers = _scrape_page(url, label)

            # Déduplication inter-catégories par URL
            new = [o for o in offers if o["url"] not in seen_urls]
            for o in new:
                seen_urls.add(o["url"])

            print(f"  [✅ Hello Work] '{label}' → {len(new)} offres")
            all_offers.extend(new)

        except Exception as e:
            print(f"  [❌ Hello Work] '{label}' erreur : {e}")

        # Pause polie entre les requêtes pour ne pas surcharger le serveur
        time.sleep(2)

    print(f"\n  [Hello Work] Total : {len(all_offers)} offres collectées")
    return all_offers