# ═══════════════════════════════════════════════════════
#  config.py — Paramètres centraux du scraper
# ═══════════════════════════════════════════════════════

# Les 6 intitulés à surveiller simultanément
JOB_TITLES = [
    "Data Scientist Junior",
    "Data Scientist",
    "Data Analyst",
    "Quantitative Analyst",
    "Business Analyst",
    "Consultant Data",
]

# Variantes de recherche par intitulé (pour couvrir les alias)
SEARCH_QUERIES = {
    "Data Scientist Junior":  ["data scientist junior", "junior data scientist"],
    "Data Scientist":         ["data scientist"],
    "Data Analyst":           ["data analyst", "analyste données"],
    "Quantitative Analyst":   ["quantitative analyst", "analyste quantitatif", "quant analyst"],
    "Business Analyst":       ["business analyst", "business data analyst"],
    "Consultant Data":        ["consultant data scientist", "consultant data", "data consultant", "consultant IA"],
}

# Paramètres fixes pour toutes les recherches
LOCATION      = "France"
CONTRACT_TYPE = "CDI"

# Sources activées
SOURCES = ["france_travail", "indeed_rss", "welcome_rss", "apec"]

# France Travail — codes typeContrat
FT_CONTRACT_CODE = "CDI"
FT_API_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
FT_API_SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

# RSS — Indeed France
INDEED_RSS_BASE = "https://fr.indeed.com/rss?q={query}&l=France&jt=fulltime&sort=date"

# RSS — Welcome to the Jungle
WTTJ_RSS_BASE = "https://www.welcometothejungle.com/fr/jobs.rss?query={query}&contract_type[]=permanent_contract&refinementList[country_code][]=FR"

# APEC
APEC_SEARCH_URL = "https://www.apec.fr/cms/webservices/rechercheOffre/rechercheOffre"
