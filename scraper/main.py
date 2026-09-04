# ═══════════════════════════════════════════════════════
#  main.py — Orchestrateur principal
#  Lancé par GitHub Actions toutes les 6h
# ═══════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════
#  main.py — Scraper France Travail + Hello Work
#  Filtres : date + handicap
#  Déduplication : titre + entreprise + ville/code postal
# ═══════════════════════════════════════════════════════

import os
import re
import sys
import hashlib
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from scraper.sources.hellowork import fetch_all as fetch_hellowork
from scraper.sources.apec import fetch_all as fetch_apec

load_dotenv()

# ── Date minimale ────────────────────────────────────
DATE_MIN = datetime(2026, 8, 17, tzinfo=timezone.utc)

# ── Mots-clés offres handicap à exclure ─────────────
HANDICAP_KEYWORDS = [
    "handicap", "handicapé", "handicapés", "handi",
    "rqth", "travailleur handicapé", "travailleurs handicapés",
    "reconnaissance qualité travailleur handicapé",
    "talents handicap", "forum handicap", "emploi handicap",
    "disability", "disabled", "inclusion handicap",
    "agefiph", "fiphfp",
]

# ── Intitulés ────────────────────────────────────────
SEARCH_QUERIES = {
    "Data Scientist Junior":  ["data scientist junior", "junior data scientist"],
    "Data Scientist":         ["data scientist", "data scientist IA ", "scientifique données", "scientifique données junior"],
    "Data Analyst":           ["data analyst", "analyste données", "analyste données junior"],
    "Quantitative Analyst":   ["quantitative analyst", "analyste quantitatif"],
    "Business Analyst":       ["business analyst", "business data analyst"],
    "Consultant Data":        ["consultant data", "consultant data scientist", "consultant IA"],
}



# ════════════════════════════════════════════════════════
#  FRANCE TRAVAIL — Token OAuth2
# ════════════════════════════════════════════════════════

def get_ft_token() -> str | None:
    client_id     = os.environ.get("FT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("FT_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("  [⚠️  France Travail] Secrets FT_CLIENT_ID / FT_CLIENT_SECRET manquants")
        return None

    print(f"  [France Travail] Client ID utilisé : {client_id[:8]}...")

    try:
        resp = requests.post(
            "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
            "?realm=%2Fpartenaire",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type":    "client_credentials",
                "client_id":     client_id,
                "client_secret": client_secret,
                "scope":         "api_offresdemploiv2 o2dsoffre",
            },
            timeout=15,
        )
        print(f"  [France Travail] Token → HTTP {resp.status_code}")
        if resp.ok:
            token = resp.json().get("access_token")
            if token:
                print("  [✅ France Travail] Token obtenu avec succès")
                return token
        else:
            print(f"  [France Travail] Réponse : {resp.text[:200]}")
    except Exception as e:
        print(f"  [France Travail] Erreur token : {e}")

    return None


# ════════════════════════════════════════════════════════
#  FRANCE TRAVAIL — Recherche d'offres
# ════════════════════════════════════════════════════════

def scrape_france_travail(query: str, label: str, token: str) -> list[dict]:
    if not token:
        return []
    try:
        resp = requests.get(
            "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={
                "motsCles":        query,
                "typeContrat":     "CDI",
                "minCreationDate": DATE_MIN.strftime("%Y-%m-%dT00:00:00Z"),
                "maxCreationDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z"),
                "range":           "0-149",
            },
            timeout=20,
        )
        if resp.status_code == 204:
            print(f"  [France Travail] '{query}' → 0 offre (204)")
            return []
        if not resp.ok:
            print(f"  [❌ France Travail] '{query}' → HTTP {resp.status_code} : {resp.text[:150]}")
            return []

        results = resp.json().get("resultats", [])
        print(f"  [✅ France Travail] '{query}' → {len(results)} offres")
        return [_normalize_ft(r, label) for r in results]

    except Exception as e:
        print(f"  [❌ France Travail] '{query}' erreur : {e}")
        return []


def _normalize_ft(r: dict, label: str) -> dict:
    # Secteur d'activite - fourni directement par France Travail
    secteur = (
        r.get("secteurActiviteLibelle")
        or r.get("entreprise", {}).get("secteurActiviteLibelle")
        or r.get("secteurActivite", "")
        or ""
    )
    # Niveau d'experience : "Debutant accepte", "1 a 3 ans", "3 a 5 ans"...
    experience = r.get("experienceLibelle", "") or ""

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
        "secteur":      secteur,
        "experience":   experience,
    }


# ════════════════════════════════════════════════════════
#  FILTRE HANDICAP
# ════════════════════════════════════════════════════════

def is_handicap_offer(offer: dict) -> bool:
    """Retourne True si l'offre est réservée aux personnes handicapées."""
    text = " ".join([
        offer.get("title",       ""),
        offer.get("company",     ""),
        offer.get("description", ""),
    ]).lower()
    return any(kw in text for kw in HANDICAP_KEYWORDS)


def filter_handicap(offers: list[dict]) -> list[dict]:
    kept, dropped = [], 0
    for o in offers:
        if is_handicap_offer(o):
            dropped += 1
        else:
            kept.append(o)
    if dropped:
        print(f"  [Filtre handicap] {dropped} offres RQTH/handicap exclues")
    return kept


# ════════════════════════════════════════════════════════
#  FILTRE DATE
# ════════════════════════════════════════════════════════

def parse_date(s: str) -> datetime | None:
    for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(s[:26], fmt)
            return dt.replace(tzinfo=timezone.utc) if not dt.tzinfo else dt
        except ValueError:
            continue
    return None


def filter_by_date(offers: list[dict]) -> list[dict]:
    kept, dropped = [], 0
    for o in offers:
        dt = parse_date(o.get("published_at", ""))
        if dt is None or dt >= DATE_MIN:
            kept.append(o)
        else:
            dropped += 1
    if dropped:
        print(f"  [Filtre date] {dropped} offres antérieures au {DATE_MIN.strftime('%d/%m/%Y')} supprimées")
    return kept


# ════════════════════════════════════════════════════════
#  DÉDUPLICATION — titre + entreprise + ville/code postal
# ════════════════════════════════════════════════════════

def _normalize_company(name: str) -> str:
    """Normaliser le nom d'entreprise."""
    n = name.lower().strip()
    for suffix in [" s.a.s.", " s.a.s", " s.a.", " sas", " sa",
                   " sarl", " s.r.l.", " srl", " groupe", " group"]:
        n = n.replace(suffix, "")
    return n.strip()


def _normalize_location(loc: str) -> str:
    """
    Extraire ville + code postal/arrondissement.
    Ex : "Paris 9e Arrondissement (75)" → "paris 75009"
         "Lyon 3e (69)"                  → "lyon 69003"
         "75009 Paris"                   → "paris 75009"
         "Levallois-Perret (92)"         → "levallois-perret 92"
    """
    loc = loc.lower().strip()

    # Code postal 5 chiffres explicite
    cp = re.search(r'\b(\d{5})\b', loc)
    if cp:
        code  = cp.group(1)
        ville = re.sub(r'\b\d{5}\b', '', loc)
        ville = re.sub(r'[(),\-]+', ' ', ville).strip()
        ville = re.sub(r'\s+', ' ', ville).strip()
        return f"{ville} {code}"

    # Département entre parenthèses ex: "(75)" "(92)"
    dep = re.search(r'\((\d{2,3})\)', loc)
    if dep:
        code_dep = dep.group(1)
        ville    = re.sub(r'\(\d{2,3}\)', '', loc)

        # Arrondissement ex: "paris 9e" → 75009
        arr = re.search(r'(\d+)e(?:r)?', ville)
        if arr and code_dep in ["75", "13", "69"]:
            num      = int(arr.group(1))
            base     = {"75": 75000, "13": 13000, "69": 69000}[code_dep]
            code_dep = str(base + num)

        ville = re.sub(r'\d+e(?:r)?\s*', '', ville)
        ville = re.sub(r'arrondissement', '', ville)
        ville = re.sub(r'[(),\s]+', ' ', ville).strip()
        return f"{ville} {code_dep}"

    # Arrondissement sans parenthèses
    arr = re.search(r'(\d+)e(?:r)?\s*arrondissement', loc)
    if arr:
        num   = int(arr.group(1))
        ville = re.sub(r'\d+e(?:r)?\s*arrondissement', '', loc).strip()
        return f"{ville} {num:02d}"

    # Ville brute nettoyée
    loc = re.sub(r'[(),]+', ' ', loc)
    return re.sub(r'\s+', ' ', loc).strip()


def make_hash(o: dict) -> str:
    """
    Hash : titre + entreprise normalisée + ville/code postal.
    → Élimine les doublons inter-sources (France Travail & Hello Work).
    → Conserve le même poste dans deux villes différentes.
    """
    title    = o.get("title",    "").lower().strip()
    company  = _normalize_company(o.get("company",  ""))
    location = _normalize_location(o.get("location", ""))
    key      = f"{title}|{company}|{location}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


# ════════════════════════════════════════════════════════
#  SUPABASE — Insertion
# ════════════════════════════════════════════════════════

def save_to_supabase(offers: list[dict]) -> int:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "").strip()

    if not url or not key:
        print("\n[⚠️  Supabase] Secrets manquants")
        return 0

    headers = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=ignore-duplicates,return=minimal",
    }

    # IDs déjà en base
    try:
        r        = requests.get(f"{url}/rest/v1/jobs?select=id&limit=10000",
                                headers=headers, timeout=15)
        existing = {row["id"] for row in r.json()} if r.ok else set()
        print(f"\n[Supabase] {len(existing)} offres déjà en base")
    except Exception as e:
        print(f"[❌ Supabase] Lecture erreur : {e}")
        existing = set()

    # Nouvelles offres uniquement
    new_offers = []
    for o in offers:
        o["id"] = make_hash(o)
        if o["id"] not in existing:
            new_offers.append(o)

    if not new_offers:
        print("[Supabase] Aucune nouvelle offre à insérer")
        return 0

    # Insertion par batch de 50
    inserted = 0
    for i in range(0, len(new_offers), 50):
        batch = new_offers[i:i+50]
        try:
            r = requests.post(f"{url}/rest/v1/jobs",
                              headers=headers, json=batch, timeout=30)
            if r.ok:
                inserted += len(batch)
                print(f"[✅ Supabase] Batch {i//50+1} : {len(batch)} offres insérées")
            else:
                print(f"[❌ Supabase] Batch {i//50+1} erreur {r.status_code} : {r.text[:200]}")
        except Exception as e:
            print(f"[❌ Supabase] Batch erreur : {e}")

    return inserted


# ════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════

def main():
    print("═" * 55)
    print("  JOB TRACKER — Data Science CDI France")
    print("  Source  : France Travail (API officielle)")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("═" * 55)

    # Vérification secrets
    print("\n── Vérification des secrets ──")
    for s in ["SUPABASE_URL", "SUPABASE_KEY", "FT_CLIENT_ID", "FT_CLIENT_SECRET"]:
        val = os.environ.get(s, "")
        print(f"  {s} : {'✅ OK' if val else '❌ MANQUANT'}")

    # Token France Travail
    print("\n── France Travail — authentification ──")
    token = get_ft_token()

    if not token:
        print("\n❌ Arrêt : impossible de contacter France Travail.")
        return 1

    # Scraping
        # Scraping France Travail
    all_offers = []
    for label, queries in SEARCH_QUERIES.items():
        print(f"\n── {label} ──")
        for query in queries:
            all_offers += scrape_france_travail(query, label, token)

    # Scraping Hello Work (une seule fois, pas par intitulé)
        # Hello Work
    print("\n── Hello Work ──")
    all_offers += fetch_hellowork()

        # APEC
    print("\n── APEC ──")
    all_offers += fetch_apec(date_min=DATE_MIN)

    # Filtre handicap
    all_offers = filter_handicap(all_offers)
    print(f"── Après filtre handicap : {len(all_offers)} offres ──")

    # Filtre date
    all_offers = filter_by_date(all_offers)
    print(f"── Après filtre date (≥ {DATE_MIN.strftime('%d/%m/%Y')}) : {len(all_offers)} offres ──")

    # Sauvegarde (déduplication par hash titre+entreprise+ville)
    inserted = save_to_supabase(all_offers)
    print(f"\n✅ Terminé — {inserted} nouvelles offres insérées dans Supabase")
    return 0


if __name__ == "__main__":
    sys.exit(main())