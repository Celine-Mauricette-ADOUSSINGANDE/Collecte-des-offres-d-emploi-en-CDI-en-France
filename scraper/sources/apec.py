import requests
import json
import time
import os
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

MOTS_CLES = "data analyst"
PAGE_SIZE = 20
OUTPUT_FILE = "apec_offres.json"

# URL APEC QUI FONCTIONNE
APEC_URL = "https://www.apec.fr/cms/webservices/rechercheOffre"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer": "https://www.apec.fr/candidat/recherche-emploi.html",
    "Origin": "https://www.apec.fr",
}


# ============================================================
# AFFICHAGE
# ============================================================

def afficher_requete(payload):
    print("\n" + "=" * 60)
    print("REQUÊTE APEC")
    print("=" * 60)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


# ============================================================
# REQUÊTE APEC
# ============================================================

def rechercher_offres(start_index=0, page_size=20):

    payload = {
        "motsCles": MOTS_CLES,
        "pagination": {
            "startIndex": start_index,
            "range": page_size
        }
    }

    afficher_requete(payload)

    try:
        response = requests.post(
            APEC_URL,
            json=payload,
            headers=HEADERS,
            timeout=30
        )

    except requests.exceptions.RequestException as e:
        print("\n❌ ERREUR RÉSEAU :")
        print(e)
        return None

    print("\nSTATUS :", response.status_code)
    print("TYPE   :", response.headers.get("content-type"))
    print("TAILLE :", len(response.text))

    # --------------------------------------------------------
    # Gestion erreurs HTTP
    # --------------------------------------------------------

    if response.status_code != 200:
        print("\n❌ ERREUR HTTP :", response.status_code)
        print("\nRéponse APEC :")
        print(response.text[:5000])
        return None

    # --------------------------------------------------------
    # Conversion JSON
    # --------------------------------------------------------

    try:
        data = response.json()
    except ValueError:
        print("\n❌ La réponse APEC n'est pas du JSON valide.")
        print(response.text[:5000])
        return None

    return data


# ============================================================
# EXTRACTION DES OFFRES
# ============================================================

def extraire_offres(data):

    if not isinstance(data, dict):
        print("❌ Réponse APEC inattendue.")
        return []

    offres = data.get("resultats", [])

    if not isinstance(offres, list):
        print("❌ Le champ 'resultats' n'est pas une liste.")
        return []

    return offres


# ============================================================
# NORMALISATION D'UNE OFFRE
# ============================================================

def normaliser_offre(offre):

    return {
        "source": "APEC",

        "id": offre.get("id"),
        "numeroOffre": offre.get("numeroOffre"),

        "intitule": offre.get("intitule"),
        "intituleSurbrillance": offre.get("intituleSurbrillance"),

        "entreprise": offre.get("nomCommercial"),

        "lieu": offre.get("lieuTexte"),

        "salaire": offre.get("salaireTexte"),

        "description": offre.get("texteOffre"),

        "dateValidation": offre.get("dateValidation"),
        "datePublication": offre.get("datePublication"),

        "latitude": offre.get("latitude"),
        "longitude": offre.get("longitude"),

        "localisable": offre.get("localisable"),

        "score": offre.get("score"),

        "offreConfidentielle": offre.get("offreConfidentielle"),

        "secteurActivite": offre.get("secteurActivite"),
        "secteurActiviteParent": offre.get("secteurActiviteParent"),

        "clientReel": offre.get("clientReel"),

        "contractDuration": offre.get("contractDuration"),
        "typeContrat": offre.get("typeContrat"),

        "origineCode": offre.get("origineCode"),

        "idNomTeletravail": offre.get("idNomTeletravail"),

        "indicateurOqa": offre.get("indicateurOqa"),
        "indicateurFaibleCandidature": offre.get(
            "indicateurFaibleCandidature"
        ),

        "urlLogo": offre.get("urlLogo"),

        "url": (
            "https://www.apec.fr/candidat/recherche-emploi.html/"
            + str(offre.get("numeroOffre"))
        ),

        "dateScraping": datetime.now().isoformat()
    }


# ============================================================
# SAUVEGARDE
# ============================================================

def sauvegarder_offres(offres):

    try:
        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                offres,
                f,
                indent=2,
                ensure_ascii=False
            )

        print("\n" + "=" * 60)
        print("SAUVEGARDE")
        print("=" * 60)

        print(f"✅ {len(offres)} offres sauvegardées")
        print(f"📁 {os.path.abspath(OUTPUT_FILE)}")

    except Exception as e:
        print("\n❌ ERREUR SAUVEGARDE :")
        print(e)


# ============================================================
# SCRAPING
# ============================================================

def scraper():

    print("=" * 60)
    print("        SCRAPER APEC")
    print("=" * 60)

    print(f"Mots-clés : {MOTS_CLES}")
    print(f"Taille page : {PAGE_SIZE}")
    print(f"Sortie : {OUTPUT_FILE}")
    print(f"\nEndpoint : {APEC_URL}")

    toutes_les_offres = []

    start_index = 0

    while True:

        print("\n" + "=" * 60)
        print(
            f"SCRAP APEC | startIndex={start_index} "
            f"| range={PAGE_SIZE}"
        )
        print("=" * 60)

        data = rechercher_offres(
            start_index=start_index,
            page_size=PAGE_SIZE
        )

        if data is None:
            print("\n❌ Arrêt du scraping")
            break

        offres = extraire_offres(data)

        print(f"\n✅ Offres reçues : {len(offres)}")

        if not offres:
            print("\nℹ️ Plus aucune offre.")
            break

        # ----------------------------------------------------
        # Ajout des offres
        # ----------------------------------------------------

        for offre in offres:

            offre_normalisee = normaliser_offre(offre)

            toutes_les_offres.append(offre_normalisee)

        # ----------------------------------------------------
        # Total annoncé par APEC
        # ----------------------------------------------------

        total_count = data.get("totalCount")

        if total_count is not None:

            print(f"📊 Total APEC : {total_count}")
            print(
                f"📥 Total récupéré : "
                f"{len(toutes_les_offres)}"
            )

            if len(toutes_les_offres) >= total_count:
                print("\n✅ Toutes les offres ont été récupérées.")
                break

        # ----------------------------------------------------
        # Si moins de PAGE_SIZE résultats :
        # dernière page
        # ----------------------------------------------------

        if len(offres) < PAGE_SIZE:

            print(
                "\nℹ️ Nombre d'offres inférieur à la taille "
                "de la page."
            )

            break

        # ----------------------------------------------------
        # Page suivante
        # ----------------------------------------------------

        start_index += PAGE_SIZE

        # Petite pause pour éviter d'enchaîner
        # trop rapidement les requêtes
        time.sleep(1)

    # --------------------------------------------------------
    # Suppression des doublons
    # --------------------------------------------------------

    offres_uniques = []

    ids_vus = set()

    for offre in toutes_les_offres:

        identifiant = (
            offre.get("numeroOffre")
            or offre.get("id")
        )

        if identifiant in ids_vus:
            continue

        ids_vus.add(identifiant)
        offres_uniques.append(offre)

    # --------------------------------------------------------
    # Sauvegarde
    # --------------------------------------------------------

    sauvegarder_offres(offres_uniques)

    print("\n" + "=" * 60)
    print("TERMINÉ")
    print("=" * 60)

    print(
        f"✅ {len(offres_uniques)} offres récupérées"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    scraper()