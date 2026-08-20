# ═══════════════════════════════════════════════════════
#  main.py — Orchestrateur principal
#  Lancé par GitHub Actions toutes les 6h
# ═══════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════
#  main.py — Scraper France Travail uniquement (API officielle)
#  APEC et RSS remplacés car bloqués depuis GitHub Actions
# ═══════════════════════════════════════════════════════

import os
import sys
import hashlib
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ── Date minimale ────────────────────────────────────
DATE_MIN = datetime(2026, 8, 17, tzinfo=timezone.utc)

# ── Intitulés ────────────────────────────────────────
SEARCH_QUERIES = {
    "Data Scientist Junior":  ["data scientist junior", "junior data scientist"],
    "Data Scientist":         ["data scientist"],
    "Data Analyst":           ["data analyst", "analyste données"],
    "Quantitative Analyst":   ["quantitative analyst", "analyste quantitatif"],
    "Business Analyst":       ["business analyst", "business data analyst"],
    "Consultant Data":        ["consultant data", "consultant data scientist", "consultant IA"],
}

# ════════════════════════════════════════════════════════
#  FRANCE TRAVAIL — Token OAuth2
#  ⚠️  URL corrigée : utilise requests.post avec Content-Type
#     application/x-www-form-urlencoded (pas de params)
# ════════════════════════════════════════════════════════

def get_ft_token() -> str | None:
    client_id     = os.environ.get("FT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("FT_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        print("  [⚠️  France Travail] Secrets FT_CLIENT_ID / FT_CLIENT_SECRET manquants")
        return None

    print(f"  [France Travail] Client ID utilisé : {client_id[:8]}...")

    # ── Tentative 1 : URL entreprise (partenaires)
    urls = [
        "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire",
        "https://francetravail.io/connexion/oauth2/access_token?realm=%2Fpartenaire",
    ]

    for url in urls:
        try:
            resp = requests.post(
                url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     client_id,
                    "client_secret": client_secret,
                    "scope":         "api_offresdemploiv2 o2dsoffre",
                },
                timeout=15,
            )
            print(f"  [France Travail] Token URL {url[:50]}... → HTTP {resp.status_code}")
            if resp.ok:
                token = resp.json().get("access_token")
                if token:
                    print("  [✅ France Travail] Token obtenu avec succès")
                    return token
            else:
                print(f"  [France Travail] Réponse : {resp.text[:200]}")
        except Exception as e:
            print(f"  [France Travail] Erreur sur {url[:50]} : {e}")

    print("  [❌ France Travail] Impossible d'obtenir un token — vérifier les credentials sur francetravail.io")
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
            headers={
                "Authorization": f"Bearer {token}",
                "Accept":        "application/json",
            },
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
            print(f"  [France Travail] '{query}' → 0 offre (204 No Content)")
            return []

        if not resp.ok:
            print(f"  [❌ France Travail] '{query}' → HTTP {resp.status_code} : {resp.text[:150]}")
            return []

        results = resp.json().get("resultats", [])
        print(f"  [✅ France Travail] '{query}' → {len(results)} offres")
        return [_normalize(r, label) for r in results]

    except Exception as e:
        print(f"  [❌ France Travail] '{query}' erreur : {e}")
        return []


def _normalize(r: dict, label: str) -> dict:
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
#  SUPABASE — Déduplication + insertion
# ════════════════════════════════════════════════════════

def make_hash(o: dict) -> str:
    key = f"{o['title'].lower().strip()}|{o['company'].lower().strip()}|{o['source']}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


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
        r = requests.get(f"{url}/rest/v1/jobs?select=id&limit=10000",
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
        print("   → Vérifier FT_CLIENT_ID et FT_CLIENT_SECRET sur francetravail.io")
        print("   → Menu 'Mes applications' → vérifier que le scope 'Offres d'emploi v2' est activé")
        return 1

    # Scraping
    all_offers = []
    for label, queries in SEARCH_QUERIES.items():
        print(f"\n── {label} ──")
        for query in queries:
            all_offers += scrape_france_travail(query, label, token)

    print(f"\n── Total brut : {len(all_offers)} offres ──")

    # Filtre date
    all_offers = filter_by_date(all_offers)
    print(f"── Après filtre date (≥ {DATE_MIN.strftime('%d/%m/%Y')}) : {len(all_offers)} offres ──")

    # Sauvegarde
    inserted = save_to_supabase(all_offers)
    print(f"\n✅ Terminé — {inserted} nouvelles offres insérées dans Supabase")
    return 0


if __name__ == "__main__":
    sys.exit(main())