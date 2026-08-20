# ═══════════════════════════════════════════════════════
#  sources/france_travail.py
#  API officielle France Travail (francetravail.io)
#  Inscription gratuite : https://francetravail.io/data/api
# ═══════════════════════════════════════════════════════

import os
import requests
from datetime import datetime, timezone
from scraper.config import FT_CONTRACT_CODE, FT_API_TOKEN_URL, FT_API_SEARCH_URL


def _get_token() -> str:
    """Obtenir un token OAuth2 France Travail."""
    resp = requests.post(
        FT_API_TOKEN_URL,
        params={"realm": "/partenaire"},
        data={
            "grant_type":    "client_credentials",
            "client_id":     os.environ["FT_CLIENT_ID"],
            "client_secret": os.environ["FT_CLIENT_SECRET"],
            "scope":         "api_offresdemploiv2 o2dsoffre",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _parse_offer(raw: dict, query_label: str) -> dict:
    """Normaliser une offre France Travail au format commun."""
    return {
        "title":        raw.get("intitule", ""),
        "company":      raw.get("entreprise", {}).get("nom", "Non précisé"),
        "location":     raw.get("lieuTravail", {}).get("libelle", "France"),
        "contract":     raw.get("typeContratLibelle", "CDI"),
        "source":       "France Travail",
        "url":          raw.get("origineOffre", {}).get("urlOrigine", ""),
        "published_at": raw.get("dateCreation", datetime.now(timezone.utc).isoformat()),
        "description":  raw.get("description", "")[:500],
        "salary":       raw.get("salaire", {}).get("libelle", ""),
        "search_label": query_label,
    }


def fetch(query: str, query_label: str) -> list[dict]:
    """
    Chercher les offres CDI France Travail pour un intitulé donné.
    Retourne une liste d'offres normalisées.
    """
    offers = []
    try:
        token = _get_token()
        headers = {"Authorization": f"Bearer {token}"}

        params = {
            "motsCles":    query,
            "typeContrat": FT_CONTRACT_CODE,
            "minCreationDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z"),
            "maxCreationDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z"),
            "range":       "0-49",  # 50 résultats max par appel
        }

        resp = requests.get(FT_API_SEARCH_URL, headers=headers, params=params, timeout=15)
        if resp.status_code == 204:
            return []  # Aucun résultat
        resp.raise_for_status()

        data = resp.json()
        for raw in data.get("resultats", []):
            offers.append(_parse_offer(raw, query_label))

        print(f"[France Travail] '{query}' → {len(offers)} offres")

    except Exception as e:
        print(f"[France Travail] Erreur pour '{query}': {e}")

    return offers
