"""
Types de champs disponibles et leurs métadonnées
"""

# ── Types de base (premier dropdown) ──────────────────────────────────────────
FIELD_BASE_TYPES = ["alpha", "num", "date", "bool", "decimal"]

# Alias pour rétrocompatibilité
FIELD_TYPES = FIELD_BASE_TYPES

# ── Sous-types par type de base ────────────────────────────────────────────────
# Format : liste de (valeur, libellé)
FIELD_SUBTYPES: dict[str, list[tuple[str, str]]] = {
    "alpha": [
        ("none", "Aucun"),
        ("email", "Email"),
        ("phone", "Téléphone"),
        ("phonePlus33", "Téléphone (+33xxx)"),
        ("civilite", "Civilité"),
        ("civiliteNir", "Civilité"),
        ("nom", "Nom"),
        ("prenom", "Prénom"),
        ("prenomNir", "Prénom"),
        ("ville", "Ville"),
        ("pays", "Pays"),
        ("adresse", "Adresse"),
        ("adresseComplete", "Adresse complète"),
        ("concat", "Concaténation"),
        ("lieuNaissance", "Lieu de naissance"),
        ("codeApe", "Code APE"),
        ("iban", "IBAN"),
    ],
    "num": [
        ("none", "Aucun"),
        ("codePostal", "Code postal"),
        ("codeInsee", "Code INSEE"),
        ("siret", "SIRET"),
        ("departement", "Département"),
        ("nir", "NIR"),
        ("compteurLignes", "Compteur de lignes"),
        ("departementNaissance", "Département de naissance"),
    ],
    "date": [
        ("none", "Aucun"),
        ("dateNaissance", "Date de naissance"),
    ],
    "bool": [
        ("none", "Aucun"),
        ("ON", "O / N"),
        ("OUINON", "OUI / NON"),
        ("OKKO", "OK / KO"),
        ("BINAIRE", "0 / 1"),
    ],
    "decimal": [],  # Pas de sous-type affiché
}

# ── Catalogue des civilités ────────────────────────────────────────────────────
CIVILITES: dict[str, list[dict]] = {
    "classiques": [
        {"code": "M", "label": "Monsieur", "gender": "M"},
        {"code": "Mme", "label": "Madame", "gender": "F"},
        {"code": "Mlle", "label": "Mademoiselle", "gender": "F", "obsolete": True},
    ],
    "administratives": [
        {"code": "M", "label": "Monsieur", "gender": "M"},
        {"code": "Mme", "label": "Madame", "gender": "F"},
        {"code": "Dr", "label": "Docteur"},
        {"code": "Pr", "label": "Professeur"},
        {"code": "Me", "label": "Maître (avocat/notaire)"},
        {"code": "Fr", "label": "Frère"},
        {"code": "Sr", "label": "Sœur"},
        {"code": "Père", "label": "Père (clergé catholique)"},
        {"code": "Abbé", "label": "Abbé"},
        {"code": "Rabbin", "label": "Rabbin"},
        {"code": "Imam", "label": "Imam"},
    ],
    "professionnelles": [
        {"code": "Dr", "label": "Docteur"},
        {"code": "Pr", "label": "Professeur"},
        {"code": "Me", "label": "Maître"},
        {"code": "Ing", "label": "Ingénieur"},
        {"code": "Dir", "label": "Directeur / Directrice"},
        {"code": "Pres", "label": "Président / Présidente"},
        {"code": "Chef", "label": "Chef / Cheffe"},
    ],
}

DATE_FORMATS = {
    "DD/MM/YYYY": "%d/%m/%Y",
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD-MM-YYYY": "%d-%m-%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYYMMDD": "%Y%m%d",
    "DDMMYYYY": "%d%m%Y",
    "timestamp": "timestamp",
    "YYYYMMDDHHmmss": "%Y%m%d%H%M%S",
    "DD/MM/YYYY HH:mm:ss": "%d/%m/%Y %H:%M:%S",
}

# Longueur fixe de la chaîne produite pour chaque format de date
DATE_FORMAT_LENGTHS: dict[str, int] = {
    "DD/MM/YYYY": 10,
    "YYYY-MM-DD": 10,
    "DD-MM-YYYY": 10,
    "MM/DD/YYYY": 10,
    "YYYYMMDD": 8,
    "DDMMYYYY": 8,
    "timestamp": 10,  # ~10 chiffres (epoch secondes)
    "YYYYMMDDHHmmss": 14,
    "DD/MM/YYYY HH:mm:ss": 19,
}

# Exemple de placeholder de saisie pour chaque format (affiché dans dateMin/dateMax)
DATE_FORMAT_PLACEHOLDERS: dict[str, str] = {
    "DD/MM/YYYY": "JJ/MM/AAAA",
    "YYYY-MM-DD": "AAAA-MM-JJ",
    "DD-MM-YYYY": "JJ-MM-AAAA",
    "MM/DD/YYYY": "MM/JJ/AAAA",
    "YYYYMMDD": "AAAAMMJJ",
    "DDMMYYYY": "JJMMAAAA",
    "timestamp": "timestamp (laisser vide)",
    "YYYYMMDDHHmmss": "AAAAMMJJHHmmss",
    "DD/MM/YYYY HH:mm:ss": "JJ/MM/AAAA HH:mm:ss",
}


# ── Configuration par défaut d'un champ ──────────────────────────────────────
DEFAULT_FIELD_CONFIG = {
    "id": "",
    "name": "",
    "type": "alpha",
    "subType": "none",
    "length": 10,
    "includeInOutput": True,
    "defaultValue": "",
    "format": "DD/MM/YYYY",
    "comment": "",
    "category": "",
    "padding": "none",
    "paddingChar": " ",
    "increment": False,
    "incrementStart": 1,
    "concatItems": [],
    "codePostalFilter": "*",
    "linkedFieldId": "",  # "" = auto | "__none__" = indépendant | <id> = lié à un champ
    "decimalSeparator": ".",
    "decimalPlaces": 2,
    # Civilité
    # classiques | administratives | professionnelles
    "civiliteCategorie": "classiques",
    "civiliteOutput": "code",  # code | label
    # Date — champ entier
    # générer la date du jour (toute la valeur)
    "todayDate": False,
    # Borne min
    "dateMinEnabled": False,  # activer la borne min
    "dateMinToday": False,  # borne min = date du jour
    # True → borne strictement supérieure (>)
    "dateMinExclusive": False,
    "dateMin": "",  # valeur fixe (si dateMinToday=False)
    # Borne max
    "dateMaxEnabled": False,  # activer la borne max
    "dateMaxToday": False,  # borne max = date du jour
    # True → borne strictement inférieure (<)
    "dateMaxExclusive": False,
    "dateMax": "",  # valeur fixe (si dateMaxToday=False)
}


# ── Configuration par (type_base, sous_type) ──────────────────────────────────
# extra_fields : champs supplémentaires affichés en plus des champs communs
# defaults     : valeurs par défaut appliquées à la sélection
SUBTYPE_CONFIG: dict[str, dict[str, dict]] = {
    "alpha": {
        "none": {
            "extra_fields": ["padding", "defaultValue"],
            "defaults": {"length": 10},
        },
        "email": {
            "extra_fields": [],
            "defaults": {"length": 50},
        },
        "phone": {
            "extra_fields": [],
            "defaults": {"length": 14},
        },
        "phonePlus33": {
            "extra_fields": [],
            "defaults": {"length": 15},
        },
        "civilite": {
            "extra_fields": ["civiliteConfig"],
            "defaults": {"length": 10, "civiliteCategorie": "classiques", "civiliteOutput": "code"},
        },
        "civiliteNir": {
            "extra_fields": ["civiliteConfig", "linkedField"],
            "defaults": {
                "length": 10,
                "civiliteCategorie": "classiques",
                "civiliteOutput": "code",
                "linkedFieldId": "",
            },
        },
        "nom": {
            "extra_fields": [],
            "defaults": {"length": 30},
        },
        "prenom": {
            "extra_fields": [],
            "defaults": {"length": 30},
        },
        "prenomNir": {
            "extra_fields": ["linkedField"],
            "defaults": {"length": 30, "linkedFieldId": ""},
        },
        "ville": {
            "extra_fields": ["codePostalFilter", "linkedField"],
            "defaults": {"length": 50, "codePostalFilter": "*", "linkedFieldId": ""},
        },
        "pays": {
            "extra_fields": [],
            "defaults": {"length": 30},
        },
        "adresse": {
            "extra_fields": [],
            "defaults": {"length": 100},
        },
        "adresseComplete": {
            "extra_fields": ["linkedField"],
            "defaults": {"length": 200, "linkedFieldId": ""},
        },
        "concat": {
            "extra_fields": ["concat"],
            "defaults": {"length": 50},
        },
        "lieuNaissance": {
            "extra_fields": ["linkedField"],
            "defaults": {"length": 30, "linkedFieldId": ""},
        },
        "codeApe": {
            "extra_fields": [],
            "defaults": {"length": 5},
        },
        "iban": {
            "extra_fields": [],
            "defaults": {"length": 27},
        },
    },
    "num": {
        "none": {
            "extra_fields": ["padding", "increment", "defaultValue"],
            "defaults": {"length": 10, "increment": False, "incrementStart": 1},
        },
        "codePostal": {
            "extra_fields": ["codePostalFilter"],
            "defaults": {"length": 5, "codePostalFilter": "*"},
        },
        "codeInsee": {
            "extra_fields": ["codePostalFilter"],
            "defaults": {"length": 5, "codePostalFilter": "*"},
        },
        "siret": {
            "extra_fields": [],
            "defaults": {"length": 14},
        },
        "departement": {
            "extra_fields": [],
            "defaults": {"length": 2},
        },
        "nir": {
            "extra_fields": [],
            "defaults": {"length": 15},
        },
        "compteurLignes": {
            "extra_fields": ["padding"],
            "defaults": {"length": 10},
        },
        "departementNaissance": {
            "extra_fields": ["linkedField"],
            "defaults": {"length": 2, "linkedFieldId": ""},
        },
    },
    "date": {
        "none": {
            "extra_fields": ["format", "todayDate", "dateRange", "defaultValue"],
            "defaults": {
                "length": 10,
                "format": "DD/MM/YYYY",
                "todayDate": False,
                "dateMinEnabled": False,
                "dateMinToday": False,
                "dateMinExclusive": False,
                "dateMin": "",
                "dateMaxEnabled": False,
                "dateMaxToday": False,
                "dateMaxExclusive": False,
                "dateMax": "",
            },
        },
        "dateNaissance": {
            "extra_fields": ["format", "dateRange", "linkedField"],
            "defaults": {
                "length": 10,
                "format": "DD/MM/YYYY",
                "dateMinEnabled": False,
                "dateMinToday": False,
                "dateMinExclusive": False,
                "dateMin": "",
                "dateMaxEnabled": False,
                "dateMaxToday": False,
                "dateMaxExclusive": False,
                "dateMax": "",
                "linkedFieldId": "",
            },
        },
    },
    "bool": {
        "none": {
            "extra_fields": ["defaultValue"],
            "defaults": {"length": 3},
        },
        "ON": {
            "extra_fields": [],
            "defaults": {"length": 1},
        },
        "OUINON": {
            "extra_fields": [],
            "defaults": {"length": 3},
        },
        "OKKO": {
            "extra_fields": [],
            "defaults": {"length": 2},
        },
        "BINAIRE": {
            "extra_fields": [],
            "defaults": {"length": 1},
        },
    },
    "decimal": {
        "none": {
            "extra_fields": ["decimal", "padding"],
            "defaults": {"length": 10, "decimalSeparator": ".", "decimalPlaces": 2},
        },
    },
}

# Clés pertinentes pour chaque (type_base, sous_type) — utilisé à l'export
# On détermine quelles clés "conditionnelles" inclure selon le sous-type
_ALWAYS_KEYS = {"id", "name", "category", "type", "subType", "length", "includeInOutput", "comment"}
_EXTRA_KEY_MAP = {
    "padding": {"padding", "paddingChar"},
    "defaultValue": {"defaultValue"},
    "format": {"format"},
    "increment": {"increment", "incrementStart"},
    "concat": {"concatItems"},
    "codePostalFilter": {"codePostalFilter"},
    "decimal": {"decimalSeparator", "decimalPlaces"},
    "civiliteConfig": {"civiliteCategorie", "civiliteOutput"},
    "dateRange": {
        "dateMin",
        "dateMinEnabled",
        "dateMinToday",
        "dateMinExclusive",
        "dateMax",
        "dateMaxEnabled",
        "dateMaxToday",
        "dateMaxExclusive",
    },
    "todayDate": {"todayDate"},
    "linkedField": {"linkedFieldId"},
}


def get_relevant_keys(base_type: str, sub_type: str) -> set[str]:
    """Retourne l'ensemble des clés pertinentes pour un champ donné."""
    sub_type = sub_type or "none"
    base_cfg = SUBTYPE_CONFIG.get(base_type, {})
    sub_cfg = base_cfg.get(sub_type, base_cfg.get("none", {}))
    extra_fields = sub_cfg.get("extra_fields", [])

    keys = set(_ALWAYS_KEYS)
    for ef in extra_fields:
        keys.update(_EXTRA_KEY_MAP.get(ef, {ef}))
    return keys


def clean_field_for_export(field: dict) -> dict:
    """Retourne le champ sans les clés non pertinentes pour son type/sous-type."""
    base_type = field.get("type", "alpha")
    sub_type = field.get("subType", "none")

    relevant = get_relevant_keys(base_type, sub_type)
    return {k: v for k, v in field.items() if k in relevant}


def get_visible_fields(base_type: str, sub_type: str = "none") -> list[str]:
    """
    Retourne la liste des champs supplémentaires visibles pour un type/sous-type.

    Returns:
        Liste des identifiants de champs extra à afficher.
    """
    sub_type = sub_type or "none"
    base_cfg = SUBTYPE_CONFIG.get(base_type, {})
    sub_cfg = base_cfg.get(sub_type, base_cfg.get("none", {}))
    return list(sub_cfg.get("extra_fields", []))


def get_field_defaults(base_type: str, sub_type: str = "none") -> dict:
    """
    Retourne les valeurs par défaut pour un type/sous-type donné.
    """
    sub_type = sub_type or "none"
    base_cfg = SUBTYPE_CONFIG.get(base_type, {})
    sub_cfg = base_cfg.get(sub_type, base_cfg.get("none", {}))
    return dict(sub_cfg.get("defaults", {}))


# ── Rétrocompatibilité : FIELD_TYPE_CONFIG (ne plus utiliser) ─────────────────
FIELD_TYPE_CONFIG: dict = {}
