# ═══════════════════════════════════════════════════════
#  sources/apec.py
#  Scraper APEC — API interne JSON
#  Basé sur le code fonctionnel fourni
#  Endpoint : https://www.apec.fr/cms/webservices/rechercheOffre
# ═══════════════════════════════════════════════════════

import re
import time
import hashlib
import requests
from datetime import datetime, timezone

APEC_URL = "https://www.apec.fr/cms/webservices/rechercheOffre"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept":       "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer":      "https://www.apec.fr/candidat/recherche-emploi.html",
    "Origin":       "https://www.apec.fr",
}

PAGE_SIZE = 100

# ── Intitulés à chercher ─────────────────────────────
SEARCH_QUERIES = {
    "Data Scientist Junior":  ["data scientist junior", "junior data scientist"],
    "Data Scientist":         ["data scientist"],
    "Data Analyst":           ["data analyst", "analyste données"],
    "Quantitative Analyst":   ["quantitative analyst", "analyste quantitatif"],
    "Business Analyst":       ["business analyst", "business data analyst"],
    "Consultant Data":        ["consultant data", "consultant data scientist", "consultant IA"],
}

# ── Mots-clés à exclure ──────────────────────────────
HANDICAP_KEYWORDS = [
    "handicap", "handicapé", "handicapés", "handi", "rqth",
    "travailleur handicapé", "travailleurs handicapés",
    "talents handicap", "forum handicap", "emploi handicap",
    "disability", "disabled", "agefiph", "fiphfp",
]

EXCLUDE_CONTRACTS = [
    "alternance", "apprentissage", "stage", "stagiaire",
    "freelance", "indépendant",
]


# ════════════════════════════════════════════════════════
#  Utilitaires
# ════════════════════════════════════════════════════════

def _norm(text) -> str:
    """Normaliser en minuscules -- accepte str, int ou None."""
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _is_handicap(text) -> bool:
    t = _norm(text)
    return any(kw in t for kw in HANDICAP_KEYWORDS)


def _is_cdi(type_contrat) -> bool:
    """
    Vérifier CDI et exclure alternance/stage.
    APEC retourne parfois un entier pour typeContrat -- on convertit.
    """
    t = _norm(type_contrat)
    if not t or t == "0":
        return True   # Pas de type précisé -> on garde
    # Exclure alternance, stage, etc.
    if any(w in t for w in EXCLUDE_CONTRACTS):
        return False
    # Garder tout le reste (CDI ou type inconnu)
    return True


def _make_hash(title: str, company: str, location: str) -> str:
    """Hash pour déduplication inter-sources."""
    key = f"{_norm(title)}|{_norm(company)}|{_norm(location)}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _parse_date(date_val) -> str:
    """Normaliser la date APEC au format ISO UTC."""
    if not date_val:
        return datetime.now(timezone.utc).isoformat()
    try:
        # Timestamp en millisecondes
        if isinstance(date_val, (int, float)):
            return datetime.fromtimestamp(
                date_val / 1000, tz=timezone.utc
            ).isoformat()
        # Chaîne "2026-08-17T10:30:00" ou "2026-08-17"
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(str(date_val)[:19], fmt)
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                continue
    except Exception:
        pass
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════
#  Requête APEC — une page de résultats
# ════════════════════════════════════════════════════════

def _fetch_page(query: str, start_index: int) -> dict | None:
    """
    Appeler l'API APEC pour une page de résultats.
    Retourne le JSON brut ou None en cas d'erreur.
    """
    payload = {
        "motsCles": query,
        "pagination": {
            "startIndex": start_index,
            "range":      PAGE_SIZE,
        },
    }
    try:
        resp = requests.post(
            APEC_URL,
            json=payload,
            headers=HEADERS,
            timeout=30,
        )
        if resp.status_code != 200:
            print(
                f"  [❌ APEC] '{query}' "
                f"page {start_index} → HTTP {resp.status_code}"
            )
            return None
        try:
            return resp.json()
        except ValueError:
            print(f"  [❌ APEC] '{query}' réponse non JSON")
            return None
    except requests.exceptions.RequestException as e:
        print(f"  [❌ APEC] '{query}' erreur réseau : {e}")
        return None


# ════════════════════════════════════════════════════════
#  Normalisation d'une offre brute APEC
# ════════════════════════════════════════════════════════

def _normalize(raw: dict, label: str) -> dict:
    """
    Convertir une offre brute APEC au format commun
    compatible avec la table Supabase.
    """
    title   = raw.get("intitule", "") or ""
    company = raw.get("nomCommercial", "") or "Non précisé"
    lieu    = raw.get("lieuTexte", "") or "France"
    numero  = raw.get("numeroOffre", "") or raw.get("id", "")

    # Nettoyer la description HTML
    desc = raw.get("texteOffre", "") or ""
    desc = re.sub(r"<[^>]+>", " ", desc)
    desc = re.sub(r"\s+", " ", desc).strip()[:500]

    # Secteur
    secteur = raw.get("secteurActivite", "") or ""

    # Salaire
    salary = raw.get("salaireTexte", "") or ""

    # Date publication
    pub_date = _parse_date(
        raw.get("datePublication") or raw.get("dateValidation")
    )

    return {
        "id":           _make_hash(title, company, lieu),
        "title":        title,
        "company":      company,
        "location":     lieu,
        "contract":     "CDI",
        "source":       "APEC",
        "url":          f"https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-annonce/{numero}.html",
        "published_at": pub_date,
        "description":  desc,
        "salary":       salary,
        "search_label": label,
        "secteur":      secteur,
        "experience":   "",
        "status":       "new",
    }


# ════════════════════════════════════════════════════════
#  Scraper complet pour un intitulé
# ════════════════════════════════════════════════════════

def _scrape_query(
    query: str,
    label: str,
    date_min: datetime,
) -> list[dict]:
    """
    Récupérer toutes les pages APEC pour un intitulé.
    Pagination automatique jusqu'à totalCount ou date_min.
    """
    offers      = []
    start_index = 0
    total_count = None

    while True:
        data = _fetch_page(query, start_index)
        if data is None:
            break

        # Total annoncé par APEC (première page uniquement)
        if total_count is None:
            total_count = data.get("totalCount", 0)
            print(
                f"  [APEC] '{query}' → "
                f"{total_count} offres annoncées"
            )

        resultats = data.get("resultats", [])
        if not resultats:
            break

        for raw in resultats:
            title   = raw.get("intitule", "") or ""
            company = raw.get("nomCommercial", "") or ""
            texte   = title + " " + company + " " + (raw.get("texteOffre", "") or "")

            # Filtre handicap
            if _is_handicap(texte):
                continue

            # Filtre contrat
            contrat = raw.get("typeContrat", "") or ""
            if not _is_cdi(contrat):
                continue

            # Filtre date
            pub_iso = _parse_date(
                raw.get("datePublication") or raw.get("dateValidation")
            )
            try:
                pub_dt = datetime.fromisoformat(
                    pub_iso.replace("Z", "+00:00")
                )
                if pub_dt < date_min:
                    continue
            except Exception:
                pass

            offers.append(_normalize(raw, label))

        # Pagination — continuer ?
        start_index += PAGE_SIZE
        fetched = start_index

        if total_count and fetched >= total_count:
            break
        if len(resultats) < PAGE_SIZE:
            break

        time.sleep(0.5)  # Pause réduite — page size plus grande

    return offers


# ════════════════════════════════════════════════════════
#  Point d'entrée appelé depuis main.py
# ════════════════════════════════════════════════════════

def fetch_all(date_min: datetime = None) -> list[dict]:
    """
    Scraper toutes les offres APEC pour les 6 intitulés.
    Appelé depuis main.py — même interface que hellowork.fetch_all().

    Args:
        date_min : datetime UTC — exclure les offres antérieures

    Returns:
        Liste d'offres normalisées et dédupliquées
    """
    if date_min is None:
        date_min = datetime(2026, 8, 17, tzinfo=timezone.utc)

    all_offers = []
    seen_ids   = set()

    for label, queries in SEARCH_QUERIES.items():
        print(f"\n  [APEC] ── {label} ──")

        for query in queries:
            offers = _scrape_query(query, label, date_min)

            # Déduplication inter-requêtes par hash
            new = [o for o in offers if o["id"] not in seen_ids]
            for o in new:
                seen_ids.add(o["id"])

            print(f"  [✅ APEC] '{query}' → {len(new)} offres retenues")
            all_offers.extend(new)

            time.sleep(0.5)

    print(f"\n  [APEC] Total : {len(all_offers)} offres collectées")
    return all_offers