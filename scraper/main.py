# ═══════════════════════════════════════════════════════
#  main.py — Orchestrateur principal
#  Lancé par GitHub Actions toutes les 6h
# ═══════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════
#  main.py — Orchestrateur avec logs de diagnostic
# ═══════════════════════════════════════════════════════

import os
import sys
import hashlib
import requests
import feedparser
from datetime import datetime, timezone
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

# ── Date minimale de publication ─────────────────────
# Seules les offres publiées à partir de cette date seront conservées
DATE_MIN = datetime(2026, 8, 17, tzinfo=timezone.utc)  # Lundi 17 août 2026

# ── Intitulés à chercher ─────────────────────────────
SEARCH_QUERIES = {
    "Data Scientist Junior":  ["data scientist junior"],
    "Data Scientist":         ["data scientist"],
    "Data Analyst":           ["data analyst"],
    "Quantitative Analyst":   ["quantitative analyst", "analyste quantitatif"],
    "Business Analyst":       ["business analyst"],
    "Consultant Data":        ["consultant data", "consultant data scientist"],
}

# ════════════════════════════════════════════════════════
#  0. FILTRE DATE
# ════════════════════════════════════════════════════════

def parse_date(date_str: str) -> datetime | None:
    """Convertir une chaîne de date en datetime timezone-aware."""
    if not date_str:
        return None
    # Formats possibles selon les sources
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str[:26], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def is_after_date_min(offer: dict) -> bool:
    """Retourne True si l'offre a été publiée après DATE_MIN."""
    dt = parse_date(offer.get("published_at", ""))
    if dt is None:
        # Date inconnue → on garde l'offre par sécurité
        return True
    return dt >= DATE_MIN


def filter_by_date(offers: list[dict]) -> list[dict]:
    """Filtrer les offres publiées avant DATE_MIN."""
    before = len(offers)
    filtered = [o for o in offers if is_after_date_min(o)]
    removed = before - len(filtered)
    if removed > 0:
        print(f"  [Filtre date] {removed} offres antérieures au {DATE_MIN.strftime('%d/%m/%Y')} supprimées")
    return filtered


# ════════════════════════════════════════════════════════
#  1. FRANCE TRAVAIL — API officielle
# ════════════════════════════════════════════════════════

def get_ft_token():
    client_id     = os.environ.get("FT_CLIENT_ID", "")
    client_secret = os.environ.get("FT_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("  [⚠️  France Travail] FT_CLIENT_ID ou FT_CLIENT_SECRET manquant dans les secrets GitHub")
        return None

    try:
        resp = requests.post(
            "https://entreprise.francetravail.fr/connexion/oauth2/access_token",
            params={"realm": "/partenaire"},
            data={
                "grant_type":    "client_credentials",
                "client_id":     client_id,
                "client_secret": client_secret,
                "scope":         "api_offresdemploiv2 o2dsoffre",
            },
            timeout=10,
        )
        resp.raise_for_status()
        print("  [✅ France Travail] Token obtenu")
        return resp.json()["access_token"]
    except Exception as e:
        print(f"  [❌ France Travail] Erreur token : {e}")
        return None


def scrape_france_travail(query, label, token):
    if not token:
        return []
    try:
        resp = requests.get(
            "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "motsCles":        query,
                "typeContrat":     "CDI",
                "minCreationDate": DATE_MIN.strftime("%Y-%m-%dT00:00:00Z"),
                "range":           "0-149",  # max 150 résultats
            },
            timeout=15,
        )
        if resp.status_code == 204:
            print(f"  [France Travail] '{query}' → 0 offre")
            return []
        resp.raise_for_status()
        results = resp.json().get("resultats", [])
        print(f"  [France Travail] '{query}' → {len(results)} offres")
        return [normalize_ft(r, label) for r in results]
    except Exception as e:
        print(f"  [❌ France Travail] '{query}' erreur : {e}")
        return []


def normalize_ft(r, label):
    return {
        "title":        r.get("intitule", ""),
        "company":      r.get("entreprise", {}).get("nom", "Non précisé"),
        "location":     r.get("lieuTravail", {}).get("libelle", "France"),
        "contract":     "CDI",
        "source":       "France Travail",
        "url":          r.get("origineOffre", {}).get("urlOrigine", ""),
        "published_at": r.get("dateCreation", datetime.now(timezone.utc).isoformat()),
        "description":  r.get("description", "")[:500],
        "salary":       r.get("salaire", {}).get("libelle", ""),
        "search_label": label,
    }

# ════════════════════════════════════════════════════════
#  2. APEC — API interne
# ════════════════════════════════════════════════════════

def scrape_apec(query, label):
    try:
        resp = requests.post(
            "https://www.apec.fr/cms/webservices/rechercheOffre/rechercheOffre",
            json={
                "motsCles":           query,
                "typeContrat":        ["CDI"],
                "nbResultatsParPage": 50,
                "debut":              0,
                "tri":                0,
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept":     "application/json",
                "Referer":    "https://www.apec.fr/",
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("resultats", [])
        print(f"  [APEC] '{query}' → {len(results)} offres")
        return [normalize_apec(r, label) for r in results]
    except Exception as e:
        print(f"  [❌ APEC] '{query}' erreur : {e}")
        return []


def normalize_apec(r, label):
    s_min = r.get("salaireMin", "")
    s_max = r.get("salaireMax", "")
    return {
        "title":        r.get("intitule", ""),
        "company":      r.get("nomEntreprise", "Non précisé"),
        "location":     r.get("lieuDeTravail", "France"),
        "contract":     "CDI",
        "source":       "APEC",
        "url":          f"https://www.apec.fr/candidat/recherche-emploi.html/emploi/{r.get('numeroOffre','')}",
        "published_at": r.get("datePublication", datetime.now(timezone.utc).isoformat()),
        "description":  r.get("accroche", "")[:500],
        "salary":       f"{s_min}–{s_max} k€/an" if s_min and s_max else "",
        "search_label": label,
    }

# ════════════════════════════════════════════════════════
#  3. RSS — Indeed & Welcome to the Jungle
# ════════════════════════════════════════════════════════

def scrape_rss(url, source, label):
    try:
        feed = feedparser.parse(url)
        entries = feed.entries
        print(f"  [{source}] '{label}' → {len(entries)} offres")
        results = []
        for e in entries:
            title = getattr(e, "title", "")
            parts = title.split(" - ")
            # Récupérer la vraie date de publication depuis le flux RSS
            pub = None
            if hasattr(e, "published_parsed") and e.published_parsed:
                try:
                    pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                except Exception:
                    pub = None
            results.append({
                "title":        parts[0].strip() if parts else title,
                "company":      parts[1].strip() if len(parts) >= 2 else "Non précisé",
                "location":     parts[2].strip() if len(parts) >= 3 else "France",
                "contract":     "CDI",
                "source":       source,
                "url":          getattr(e, "link", ""),
                "published_at": pub or datetime.now(timezone.utc).isoformat(),
                "description":  getattr(e, "summary", "")[:500],
                "salary":       "",
                "search_label": label,
            })
        return results
    except Exception as e:
        print(f"  [❌ {source}] erreur : {e}")
        return []

# ════════════════════════════════════════════════════════
#  4. DÉDUPLICATION & SUPABASE
# ════════════════════════════════════════════════════════

def make_hash(offer):
    key = f"{offer['title'].lower().strip()}|{offer['company'].lower().strip()}|{offer['source']}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def save_to_supabase(offers):
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        print("\n[⚠️  Supabase] SUPABASE_URL ou SUPABASE_KEY manquant dans les secrets GitHub")
        return 0

    headers = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=ignore-duplicates",
    }

    # Récupérer les IDs déjà en base
    try:
        r = requests.get(f"{url}/rest/v1/jobs?select=id", headers=headers, timeout=10)
        existing = {row["id"] for row in r.json()} if r.ok else set()
        print(f"\n[Supabase] {len(existing)} offres déjà en base")
    except Exception as e:
        print(f"[❌ Supabase] Erreur lecture : {e}")
        existing = set()

    # Ajouter le hash id à chaque offre
    new_offers = []
    for o in offers:
        o["id"] = make_hash(o)
        if o["id"] not in existing:
            new_offers.append(o)

    if not new_offers:
        print("[Supabase] Aucune nouvelle offre à insérer")
        return 0

    # Insérer par batch de 50
    inserted = 0
    for i in range(0, len(new_offers), 50):
        batch = new_offers[i:i+50]
        try:
            r = requests.post(
                f"{url}/rest/v1/jobs",
                headers=headers,
                json=batch,
                timeout=20,
            )
            if r.ok:
                inserted += len(batch)
                print(f"[Supabase] Batch {i//50+1} : {len(batch)} offres insérées ✅")
            else:
                print(f"[❌ Supabase] Batch {i//50+1} erreur {r.status_code} : {r.text[:200]}")
        except Exception as e:
            print(f"[❌ Supabase] Batch erreur : {e}")

    return inserted

# ════════════════════════════════════════════════════════
#  5. MAIN
# ════════════════════════════════════════════════════════

def main():
    print("═" * 55)
    print("  JOB TRACKER — Data Science CDI France")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("═" * 55)

    # Vérification des secrets
    print("\n── Vérification des secrets ──")
    secrets = ["SUPABASE_URL","SUPABASE_KEY","FT_CLIENT_ID","FT_CLIENT_SECRET"]
    for s in secrets:
        val = os.environ.get(s, "")
        status = "✅ OK" if val else "❌ MANQUANT"
        print(f"  {s} : {status}")

    all_offers = []

    # Token France Travail (un seul pour tous les appels)
    print("\n── France Travail — authentification ──")
    ft_token = get_ft_token()

    # Scraping par intitulé
    for label, queries in SEARCH_QUERIES.items():
        print(f"\n── {label} ──")
        for query in queries:
            all_offers += scrape_france_travail(query, label, ft_token)
            all_offers += scrape_apec(query, label)
            all_offers += scrape_rss(
                f"https://fr.indeed.com/rss?q={quote_plus(query+' CDI')}&l=France&sort=date",
                "Indeed", label
            )
            all_offers += scrape_rss(
                f"https://www.welcometothejungle.com/fr/jobs.rss?query={quote_plus(query)}&contract_type[]=permanent_contract",
                "Welcome to the Jungle", label
            )

    print(f"\n── Total brut collecté : {len(all_offers)} offres ──")

    # Filtre par date — uniquement à partir du 17/08/2026
    all_offers = filter_by_date(all_offers)
    print(f"── Après filtre date (≥ {DATE_MIN.strftime('%d/%m/%Y')}) : {len(all_offers)} offres ──")

    # Sauvegarde
    inserted = save_to_supabase(all_offers)

    print(f"\n✅ Terminé — {inserted} nouvelles offres insérées dans Supabase")
    return 0


if __name__ == "__main__":
    sys.exit(main())