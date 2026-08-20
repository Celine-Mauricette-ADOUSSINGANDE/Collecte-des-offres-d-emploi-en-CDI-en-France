# ═══════════════════════════════════════════════════════
#  storage.py
#  Déduplication par hash + upsert dans Supabase
# ═══════════════════════════════════════════════════════
#
#  SQL à exécuter UNE FOIS dans Supabase > SQL Editor :
#
#  CREATE TABLE IF NOT EXISTS jobs (
#    id           TEXT PRIMARY KEY,          -- hash SHA-256
#    title        TEXT NOT NULL,
#    company      TEXT,
#    location     TEXT,
#    contract     TEXT,
#    source       TEXT,
#    url          TEXT,
#    published_at TIMESTAMPTZ,
#    description  TEXT,
#    salary       TEXT,
#    search_label TEXT,
#    status       TEXT DEFAULT 'new',        -- new / saved / applied / interview / rejected
#    created_at   TIMESTAMPTZ DEFAULT now()
#  );
#
#  -- Index pour les requêtes du dashboard
#  CREATE INDEX IF NOT EXISTS jobs_created_at_idx ON jobs(created_at DESC);
#  CREATE INDEX IF NOT EXISTS jobs_status_idx     ON jobs(status);
#  CREATE INDEX IF NOT EXISTS jobs_source_idx     ON jobs(source);
# ═══════════════════════════════════════════════════════

import os
import hashlib
from datetime import datetime, timezone
from supabase import create_client, Client


def _get_client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )


def _make_hash(offer: dict) -> str:
    """
    Identifiant unique basé sur titre + entreprise + source.
    Deux offres identiques publiées sur deux plateformes
    obtiennent des hash différents (on les garde toutes).
    """
    key = f"{offer['title'].lower().strip()}|{offer['company'].lower().strip()}|{offer['source']}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def deduplicate(offers: list[dict]) -> list[dict]:
    """
    Supprimer les doublons dans le lot courant
    (même titre + même entreprise + même source).
    """
    seen = set()
    unique = []
    for offer in offers:
        h = _make_hash(offer)
        if h not in seen:
            seen.add(h)
            offer["id"] = h
            unique.append(offer)
    return unique


def save_new_offers(offers: list[dict]) -> list[dict]:
    """
    Upsert les offres dans Supabase.
    - Les nouvelles sont insérées avec status='new'.
    - Les existantes sont ignorées (on_conflict=ignore)
      pour ne pas écraser le statut mis à jour manuellement.
    Retourne uniquement les offres réellement nouvelles.
    """
    if not offers:
        return []

    client = _get_client()

    # Récupérer les IDs déjà en base
    existing_ids = set()
    res = client.table("jobs").select("id").execute()
    for row in res.data:
        existing_ids.add(row["id"])

    new_offers = [o for o in offers if o["id"] not in existing_ids]

    if new_offers:
        # Upsert par batch de 100
        for i in range(0, len(new_offers), 100):
            batch = new_offers[i:i+100]
            client.table("jobs").upsert(batch, on_conflict="id").execute()
        print(f"[Supabase] {len(new_offers)} nouvelles offres insérées.")
    else:
        print("[Supabase] Aucune nouvelle offre.")

    return new_offers


def get_stats() -> dict:
    """Récupérer les stats globales pour le résumé email."""
    client = _get_client()
    res = client.table("jobs").select("status, source").execute()
    rows = res.data

    return {
        "total":     len(rows),
        "by_status": _count_by(rows, "status"),
        "by_source": _count_by(rows, "source"),
    }


def _count_by(rows: list[dict], key: str) -> dict:
    counts = {}
    for row in rows:
        v = row.get(key, "unknown")
        counts[v] = counts.get(v, 0) + 1
    return counts
