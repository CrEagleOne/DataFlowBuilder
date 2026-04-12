"""
Constantes utilisées dans l'application
"""

# URL de l'API Geo du gouvernement français
GEO_API_URL = "https://geo.api.gouv.fr"

# Communes de fallback en cas d'échec de l'API
FALLBACK_COMMUNES = [
    {
        "nom": "Paris",
        "code": "75056",
        "codesPostaux": [
            "75001",
            "75002",
            "75003",
            "75004",
            "75005",
            "75006",
            "75007",
            "75008",
            "75009",
            "75010",
            "75011",
            "75012",
            "75013",
            "75014",
            "75015",
            "75016",
            "75017",
            "75018",
            "75019",
            "75020",
        ],
        "codeDepartement": "75",
    },
    {
        "nom": "Marseille",
        "code": "13055",
        "codesPostaux": [
            "13001",
            "13002",
            "13003",
            "13004",
            "13005",
            "13006",
            "13007",
            "13008",
            "13009",
            "13010",
            "13011",
            "13012",
            "13013",
            "13014",
            "13015",
            "13016",
        ],
        "codeDepartement": "13",
    },
    {
        "nom": "Lyon",
        "code": "69123",
        "codesPostaux": [
            "69001",
            "69002",
            "69003",
            "69004",
            "69005",
            "69006",
            "69007",
            "69008",
            "69009",
        ],
        "codeDepartement": "69",
    },
    {
        "nom": "Toulouse",
        "code": "31555",
        "codesPostaux": ["31000", "31100", "31200", "31300", "31400", "31500"],
        "codeDepartement": "31",
    },
    {
        "nom": "Nice",
        "code": "06088",
        "codesPostaux": ["06000", "06100", "06200", "06300"],
        "codeDepartement": "06",
    },
    {
        "nom": "Nantes",
        "code": "44109",
        "codesPostaux": ["44000", "44100", "44200", "44300"],
        "codeDepartement": "44",
    },
    {
        "nom": "Bordeaux",
        "code": "33063",
        "codesPostaux": ["33000", "33100", "33200", "33300", "33800"],
        "codeDepartement": "33",
    },
    {
        "nom": "Lille",
        "code": "59350",
        "codesPostaux": ["59000", "59160", "59260", "59777", "59800"],
        "codeDepartement": "59",
    },
    {
        "nom": "Rennes",
        "code": "35238",
        "codesPostaux": ["35000", "35200", "35700"],
        "codeDepartement": "35",
    },
    {
        "nom": "Strasbourg",
        "code": "67482",
        "codesPostaux": ["67000", "67100", "67200"],
        "codeDepartement": "67",
    },
]
