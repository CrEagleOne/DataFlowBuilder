"""
Générateur de données pour les différents types de champs
"""

import calendar
import logging
import random
from datetime import datetime, timedelta
from typing import cast

from faker import Faker

from core.field_types import (
    CIVILITES,
    DATE_FORMATS,
)

# Initialisation de Faker en français
fake = Faker("fr_FR")

try:
    from .geo_api import GeoAPIClient

    _geo_client_class: type[GeoAPIClient] | None = GeoAPIClient
except ImportError:
    _geo_client_class = None


class DataGenerator:
    """Classe responsable de la génération de données"""

    def __init__(self, storage_manager=None):
        self.increment_counters = {}
        self.geo_client = None
        self._counters = {}
        if _geo_client_class and storage_manager:
            self.geo_client = _geo_client_class(storage_manager)

    def reset_counters(self):
        self.increment_counters = {}
        self._counters = {}

    # ─── Résolution type/subType ───────────────────────────────────────────────

    @staticmethod
    def _resolve_type(field: dict) -> tuple[str, str]:
        """
        Retourne (base_type, sub_type) en tenant compte de la rétrocompatibilité.
        """
        base = field.get("type", "alpha")
        sub = field.get("subType", "none") or "none"

        return base, sub

    # ─── Point d'entrée principal ─────────────────────────────────────────────

    def generate_field_value(
        self,
        field: dict,
        row_index: int,
        all_fields_data: dict | None = None,
        field_presets: dict | None = None,
        total_lines: int | None = None,
    ) -> str:
        field_id = field["id"]
        base_type, sub_type = self._resolve_type(field)
        length = field.get("length", 10)

        # ── Cas spéciaux (priorité absolue) ──
        if sub_type == "compteurLignes":
            value = str(total_lines) if total_lines is not None else "0"

        elif sub_type == "concat":
            value = self._generate_concat_value(field, all_fields_data)

        # ── Incrément ──
        elif field.get("increment") and base_type == "num" and sub_type == "none":
            value = self._generate_increment_value(field, field_id)

        # ── Presets ──
        elif (
            field_presets
            and field_id in field_presets
            and not field_presets[field_id].get("useRandom", True)
        ):
            values = field_presets[field_id].get("values", [])
            value = random.choice(values)["value"] if values else field.get("defaultValue", "VALUE")

        # ── Génération aléatoire ──
        else:
            value = self._generate_random_value(base_type, sub_type, field, all_fields_data)

        # ── Padding ──
        value_str = str(value)
        if len(value_str) < length:
            padding = field.get("padding", "none")
            padding_char = field.get("paddingChar", " ")
            if padding == "before":
                value_str = value_str.rjust(length, padding_char)
            elif padding == "after":
                value_str = value_str.ljust(length, padding_char)
            elif padding == "both":
                total_pad = length - len(value_str)
                left_pad = total_pad // 2
                right_pad = total_pad - left_pad
                value_str = padding_char * left_pad + value_str + padding_char * right_pad

        if len(value_str) > length:
            value_str = value_str[:length]

        return value_str

    # ─── Concaténation ────────────────────────────────────────────────────────

    def _generate_concat_value(self, field: dict, all_fields_data: dict | None) -> str:
        parts = []
        for item in field.get("concatItems", []):
            if item["type"] == "field":
                ref_id = item["fieldId"]
                if all_fields_data and ref_id in all_fields_data:
                    parts.append(str(all_fields_data[ref_id]))
            elif item["type"] == "text":
                parts.append(item.get("value", ""))
        return "".join(parts)

    # ─── Incrément ────────────────────────────────────────────────────────────

    def _generate_increment_value(self, field: dict, field_id: str) -> str:
        if field_id not in self._counters:
            default = field.get("defaultValue", "")
            start = int(default) if default else int(field.get("incrementStart", 1))
            self._counters[field_id] = start
            return str(start)

        self._counters[field_id] += 1
        return str(self._counters[field_id])

    # ─── Génération aléatoire ─────────────────────────────────────────────────

    def _generate_random_value(
        self,
        base_type: str,
        sub_type: str,
        field: dict,
        all_fields_data: dict | None = None,
    ) -> str:
        """Dispatch vers la méthode de génération appropriée."""
        if base_type == "alpha":
            return self._gen_alpha(sub_type, field, all_fields_data)
        elif base_type == "num":
            return self._gen_num(sub_type, field, all_fields_data)
        elif base_type == "date":
            return self._gen_date(sub_type, field, all_fields_data)
        elif base_type == "bool":
            return self._gen_bool(sub_type)
        elif base_type == "decimal":
            return self._gen_decimal(field)
        return "VALUE"

    # ─── NIR : génération et parsing ─────────────────────────────────────────

    def _build_nir(self) -> dict:
        """
        Génère un NIR complet (15 chiffres) et retourne ses composants.

        Structure NIR :
          [0]     sexe         (1=M, 2=F)
          [1:3]   annee        (2 chiffres, ex: 85)
          [3:5]   mois         (01-12)
          [5:7]   departement  (01-95, zfill 2)
          [7:10]  commune      (3 chiffres)
          [10:13] ordre        (3 chiffres)
          [13:15] cle          (2 chiffres)
        """
        sexe = random.choice(["1", "2"])
        annee = str(random.randint(0, 99)).zfill(2)
        mois = str(random.randint(1, 12)).zfill(2)
        dept = str(random.randint(1, 95)).zfill(2)
        commune = str(random.randint(1, 999)).zfill(3)
        ordre = str(random.randint(1, 999)).zfill(3)
        cle = str(random.randint(0, 99)).zfill(2)
        nir = sexe + annee + mois + dept + commune + ordre + cle  # 15 chars

        # Année complète : heuristique simple (>= 30 → 19xx, sinon 20xx)
        annee_int = int(annee)
        annee_full = (1900 if annee_int >= 30 else 2000) + annee_int

        return {
            "nir": nir,
            "sexe": sexe,
            "annee": annee,
            "annee_full": annee_full,
            "mois": mois,
            "departement": dept,
            "commune": commune,
        }

    @staticmethod
    def _parse_nir(nir_str: str) -> dict | None:
        """
        Tente de parser un NIR déjà généré.
        Retourne None si la chaîne ne correspond pas au format attendu.
        """
        s = "".join(c for c in nir_str if c.isdigit())
        if len(s) < 13:
            return None
        sexe = s[0]
        annee = s[1:3]
        mois = s[3:5]
        dept = s[5:7]
        commune = s[7:10]

        annee_int = int(annee)
        annee_full = (1900 if annee_int >= 30 else 2000) + annee_int

        # Validation minimale
        if sexe not in ("1", "2"):
            return None
        if not (1 <= int(mois) <= 12):
            return None
        if not (1 <= int(dept) <= 99):
            return None

        return {
            "sexe": sexe,
            "annee": annee,
            "annee_full": annee_full,
            "mois": mois,
            "departement": dept,
            "commune": commune,
        }

    def _get_or_create_nir_data(self, field: dict, all_fields_data: dict | None) -> dict:
        """
        Retourne les composants NIR à utiliser pour le champ donné.

        Comportement selon linkedFieldId du champ :
          - "__none__" → NIR indépendant généré à la volée (pas de cache)
          - <id>       → lié au champ dont l'ID est <id> (cache par ID)
          - ""         → auto-détection (comportement historique, cache global)
        """
        linked_id = field.get("linkedFieldId", "")

        # ── Indépendant : NIR temporaire, pas mis en cache ────────────────────
        if linked_id == "__none__":
            return self._build_nir()

        # ── Lié à un champ spécifique ─────────────────────────────────────────
        if linked_id:
            cache_key = f"_nir_data_{linked_id}"
            if all_fields_data and cache_key in all_fields_data:
                return cast("dict", all_fields_data[cache_key])
            parsed = None
            if all_fields_data and linked_id in all_fields_data:
                parsed = self._parse_nir(all_fields_data[linked_id])
            if parsed is None:
                parsed = self._build_nir()
            if all_fields_data is not None:
                all_fields_data[cache_key] = parsed
            return parsed

        # ── Auto-détection (cache global) ─────────────────────────────────────
        if all_fields_data and "_nir_data" in all_fields_data:
            return cast("dict", all_fields_data["_nir_data"])

        parsed = None
        if all_fields_data:
            nir_field_id = all_fields_data.get("_nir_field_id")
            if nir_field_id and nir_field_id in all_fields_data:
                parsed = self._parse_nir(all_fields_data[nir_field_id])
            if parsed is None:
                for key, val in all_fields_data.items():
                    if key.startswith("_"):
                        continue
                    if isinstance(val, str) and len("".join(c for c in val if c.isdigit())) == 15:
                        candidate = self._parse_nir(val)
                        if candidate:
                            parsed = candidate
                            break

        if parsed is None:
            parsed = self._build_nir()

        if all_fields_data is not None:
            all_fields_data["_nir_data"] = parsed

        return parsed

    def _get_or_create_cp_data(self, field: dict, all_fields_data: dict | None) -> dict | None:
        """
        Retourne les données de code postal liées au champ donné.

        Comportement selon linkedFieldId du champ :
          - "__none__" → indépendant, pas de lookup CP (retourne None)
          - <id>       → lié au champ dont l'ID est <id> (cache par ID)
          - ""         → auto-détection (comportement historique, cache global)
        """
        linked_id = field.get("linkedFieldId", "")

        # ── Indépendant ───────────────────────────────────────────────────────
        if linked_id == "__none__":
            return None

        # ── Lié à un champ spécifique ─────────────────────────────────────────
        if linked_id:
            cache_key = f"_cp_data_{linked_id}"
            if all_fields_data and cache_key in all_fields_data:
                return dict(all_fields_data[cache_key])
            cp_value = None
            if all_fields_data and linked_id in all_fields_data:
                cp_value = all_fields_data[linked_id]
            if not cp_value:
                return None
            commune = None
            if self.geo_client:
                try:
                    commune = self.geo_client.get_commune_par_code_postal(str(cp_value))
                except Exception:
                    logger.warning("Geo lookup failed, using fallback", exc_info=True)
            result = {"codePostal": cp_value, "commune": commune}
            if all_fields_data is not None:
                all_fields_data[cache_key] = result
            return result

        # ── Auto-détection (cache global) ─────────────────────────────────────
        if all_fields_data and "_cp_data" in all_fields_data:
            return dict(all_fields_data["_cp_data"])

        cp_value = None
        if all_fields_data:
            cp_field_id = all_fields_data.get("_cp_field_id")
            if cp_field_id and cp_field_id in all_fields_data:
                cp_value = all_fields_data[cp_field_id]

        if not cp_value:
            return None

        commune = None
        if self.geo_client:
            try:
                commune = self.geo_client.get_commune_par_code_postal(cp_value)
            except Exception:
                logger.warning("Geo lookup failed, using fallback", exc_info=True)

        result = {"codePostal": cp_value, "commune": commune}
        if all_fields_data is not None:
            all_fields_data["_cp_data"] = result
        return result

    # ── alpha ──────────────────────────────────────────────────────────────────

    def _gen_alpha(self, sub_type: str, field: dict, all_fields_data: dict | None = None) -> str:
        length = field.get("length", 10)
        if sub_type == "none":
            dv = field.get("defaultValue", "")
            return str(dv) if dv else str(fake.lexify("?" * min(length, 20)))
        elif sub_type == "email":
            return str(fake.email())
        elif sub_type == "phone":
            return str(fake.phone_number())
        elif sub_type == "phonePlus33":
            digits = fake.numerify("#########")
            return f"+33 {digits[0]} {digits[1:3]} {digits[3:5]} {digits[5:7]} {digits[7:9]}"
        elif sub_type == "civilite":
            return self._gen_civilite(field)
        elif sub_type == "civiliteNir":
            return self._gen_civilite_nir(field, all_fields_data)
        elif sub_type == "nom":
            return str(fake.last_name())
        elif sub_type == "prenom":
            return str(fake.first_name())
        elif sub_type == "prenomNir":
            return self._gen_prenom_nir(field, all_fields_data)
        elif sub_type == "ville":
            return self._gen_ville(field, all_fields_data)
        elif sub_type == "pays":
            return "France"
        elif sub_type == "adresse":
            return str(fake.street_address())
        elif sub_type == "adresseComplete":
            return self._gen_adresse_complete(field, all_fields_data)
        elif sub_type == "lieuNaissance":
            nir_data = self._get_or_create_nir_data(field, all_fields_data)
            dept = str(nir_data.get("departement", "*"))
            virtual_field = {**field, "codePostalFilter": dept + "*"}
            return self._gen_ville(virtual_field)
        elif sub_type == "iban":
            return str(fake.iban())
        elif sub_type == "codeApe":
            return str(fake.numerify("####")) + random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        return str(fake.lexify("?" * min(length, 20)))

    def _gen_civilite(self, field: dict, sexe: str | None = None) -> str:
        """
        Génère une civilité selon la catégorie et le format de sortie configurés.

        Args:
            field: Configuration du champ (civiliteCategorie, civiliteOutput).
            sexe:  '1' = masculin, '2' = féminin, None = aléatoire parmi tous.
        """
        cat = field.get("civiliteCategorie", "classiques")
        output_key = field.get("civiliteOutput", "code")
        items = CIVILITES.get(cat, CIVILITES["classiques"])

        if sexe is not None:
            # Filtrer par genre si possible
            gender_map = {"1": "M", "2": "F"}
            gender = gender_map.get(sexe)
            gendered = [it for it in items if it.get("gender") == gender]
            # Si aucun item genré dans cette catégorie, prendre tous
            pool = gendered if gendered else items
        else:
            pool = items

        chosen = random.choice(pool)
        return str(chosen.get(output_key, chosen.get("code", "?")))

    def _gen_civilite_nir(self, field: dict, all_fields_data: dict | None) -> str:
        """Génère une civilité cohérente avec le sexe du NIR."""
        nir_data = self._get_or_create_nir_data(field, all_fields_data)
        sexe = str(nir_data.get("sexe", random.choice(["1", "2"])))
        return self._gen_civilite(field, sexe=sexe)

    def _gen_prenom_nir(self, field: dict, all_fields_data: dict | None) -> str:
        """Génère un prénom cohérent avec le sexe du NIR."""
        nir_data = self._get_or_create_nir_data(field, all_fields_data)
        sexe = str(nir_data.get("sexe", random.choice(["1", "2"])))
        f = Faker("fr_FR")
        return str(f.first_name_male()) if sexe == "1" else str(f.first_name_female())

    # ── num ────────────────────────────────────────────────────────────────────

    def _gen_num(self, sub_type: str, field: dict, all_fields_data: dict | None = None) -> str:
        length = field.get("length", 10)
        if sub_type == "none":
            dv = field.get("defaultValue", "")
            return str(dv) if dv else str(fake.numerify("#" * min(length, 20)))
        elif sub_type == "codePostal":
            return self._gen_code_postal(field)
        elif sub_type == "codeInsee":
            return self._gen_code_insee(field)
        elif sub_type == "siret":
            return str(fake.numerify("##############"))
        elif sub_type == "departement":
            return str(random.randint(1, 95)).zfill(2)
        elif sub_type == "departementNaissance":
            nir_data = self._get_or_create_nir_data(field, all_fields_data)
            return str(nir_data.get("departement", str(random.randint(1, 95)).zfill(2)))
        elif sub_type == "nir":
            nir_data = self._build_nir()
            # Stocker les composants pour que les champs dépendants les utilisent
            if all_fields_data is not None:
                all_fields_data["_nir_data"] = nir_data
            return str(nir_data["nir"])
        elif sub_type == "compteurLignes":
            # Géré en amont via total_lines, ne devrait pas arriver ici
            return "0"
        return str(fake.numerify("#" * min(length, 20)))

    # ── date ───────────────────────────────────────────────────────────────────

    def _gen_date(self, sub_type: str, field: dict, all_fields_data: dict | None = None) -> str:
        date_format = field.get("format", "DD/MM/YYYY")
        fmt = DATE_FORMATS.get(str(date_format), "%d/%m/%Y")

        if sub_type == "dateNaissance":
            nir_data = self._get_or_create_nir_data(field, all_fields_data)
            annee_full = int(nir_data.get("annee_full", 1985))
            mois = int(nir_data.get("mois", 1))

            max_day = calendar.monthrange(annee_full, mois)[1]
            jour = random.randint(1, max_day)
            date_obj = datetime(annee_full, mois, jour)
        elif field.get("todayDate", False):
            date_obj = datetime.now()
        else:
            # Sous-type 'none' — plage optionnelle via dateMin/dateMax
            date_obj = self._random_date_in_range(field)

        if fmt == "timestamp":
            return str(calendar.timegm(date_obj.timetuple()))
        return str(date_obj.strftime(fmt))

    def _random_date_in_range(self, field: dict) -> datetime:
        """
        Génère une date aléatoire en respectant les bornes min/max configurées.

        Chaque borne dispose de :
        - *Enabled*   : borne active ou non
        - *Today*     : borne = date du jour (prioritaire sur la valeur fixe)
        - *Exclusive* : True → strict (> / <) | False → inclusif (≥ / ≤)
        """

        fmt_key = field.get("format", "DD/MM/YYYY")
        py_fmt = DATE_FORMATS.get(fmt_key, "%d/%m/%Y")
        if py_fmt == "timestamp":
            py_fmt = "%d/%m/%Y"

        # Tous les formats connus pour le parsing
        _PARSE_FMTS = [f for f in DATE_FORMATS.values() if f != "timestamp"]

        def _try_parse(s: str) -> datetime | None:
            for f in [py_fmt] + _PARSE_FMTS:
                try:
                    return datetime.strptime(s, f)
                except ValueError:
                    pass
            return None

        # ── Borne min ─────────────────────────────────────────────────────────
        d_min = None
        min_excl = False
        if field.get("dateMinEnabled", False):
            min_excl = field.get("dateMinExclusive", False)
            if field.get("dateMinToday", False):
                d_min = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                raw = field.get("dateMin", "").strip()
                if raw:
                    d_min = _try_parse(raw)

        # ── Borne max ─────────────────────────────────────────────────────────
        d_max = None
        max_excl = False
        if field.get("dateMaxEnabled", False):
            max_excl = field.get("dateMaxExclusive", False)
            if field.get("dateMaxToday", False):
                d_max = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                raw = field.get("dateMax", "").strip()
                if raw:
                    d_max = _try_parse(raw)

        # ── Valeurs par défaut si borne non activée ───────────────────────────
        if d_min is None:
            d_min = datetime(1940, 1, 1)
            min_excl = False
        if d_max is None:
            d_max = datetime.now()
            max_excl = False

        # ── Application de l'exclusivité ──────────────────────────────────────
        # Borne exclusive → on décale d'un jour pour sortir la valeur limite
        eff_min = d_min + timedelta(days=1) if min_excl else d_min
        eff_max = d_max - timedelta(days=1) if max_excl else d_max

        # Clamp si incohérent
        if eff_min > eff_max:
            eff_min, eff_max = eff_max, eff_min

        delta_days = (eff_max - eff_min).days
        if delta_days <= 0:
            return eff_min
        return eff_min + timedelta(days=random.randint(0, delta_days))

    # ── bool ───────────────────────────────────────────────────────────────────

    def _gen_bool(self, sub_type: str) -> str:
        if sub_type == "ON":
            return random.choice(["O", "N"])
        elif sub_type == "OUINON":
            return random.choice(["OUI", "NON"])
        elif sub_type == "OKKO":
            return random.choice(["OK", "KO"])
        elif sub_type == "BINAIRE":
            return random.choice(["0", "1"])
        # none
        return random.choice(["OUI", "NON"])

    # ── decimal ────────────────────────────────────────────────────────────────

    def _gen_decimal(self, field: dict) -> str:
        places = field.get("decimalPlaces", 2)
        separator = field.get("decimalSeparator", ".")
        val = f"{random.uniform(0, 1000):.{places}f}"
        if separator != ".":
            val = val.replace(".", separator)
        return val

    # ── Géo ────────────────────────────────────────────────────────────────────

    def _gen_code_postal(self, field: dict) -> str:
        filtre = str(field.get("codePostalFilter", "*"))
        if self.geo_client:
            try:
                return str(self.geo_client.get_code_postal_aleatoire(filtre))
            except Exception as exc:
                logger.debug("GeoAPI code postal: %s", exc)
        if filtre == "*":
            return str(fake.postcode())
        elif filtre.endswith("*"):
            prefix = filtre[:-1]
            return prefix + str(fake.numerify("#" * (5 - len(prefix))))
        return str(fake.postcode())

    def _gen_code_insee(self, field: dict) -> str:
        filtre = str(field.get("codePostalFilter", "*"))
        if self.geo_client:
            try:
                cp = self.geo_client.get_code_postal_aleatoire(filtre)
                commune = self.geo_client.get_commune_par_code_postal(cp)
                if commune:
                    return str(commune.get("code", fake.numerify("#####")))
            except Exception as exc:
                logger.debug("GeoAPI code INSEE: %s", exc)
        return str(fake.numerify("#####"))

    def _gen_ville(self, field: dict, all_fields_data: dict | None = None) -> str:
        # Priorité 1 : commune liée au codePostal configuré sur CE champ
        cp_data = self._get_or_create_cp_data(field, all_fields_data)
        if cp_data and cp_data.get("commune"):
            return str(cp_data["commune"].get("nom", fake.city()))

        # Priorité 2 : filtre codePostal propre au champ
        filtre = str(field.get("codePostalFilter", "*"))
        if self.geo_client:
            try:
                if filtre != "*":
                    cp = self.geo_client.get_code_postal_aleatoire(filtre)
                    commune = self.geo_client.get_commune_par_code_postal(cp)
                    if commune:
                        return str(commune.get("nom", fake.city()))
                commune = self.geo_client.get_commune_aleatoire(fake)
                return str(commune.get("nom", fake.city()))
            except Exception:
                logger.warning("Geo lookup failed, using fallback", exc_info=True)
        return str(fake.city())

    def _gen_adresse_complete(self, field: dict, all_fields_data: dict | None = None) -> str:
        """Génère une adresse complète cohérente avec le codePostal lié si configuré."""
        cp_data = self._get_or_create_cp_data(field, all_fields_data)
        if cp_data:
            cp = str(cp_data.get("codePostal", ""))
            commune = cp_data.get("commune")
            ville = str(commune.get("nom", fake.city())) if commune else str(fake.city())
            return f"{fake.street_address()}, {cp} {ville}"
        return str(fake.address()).replace("\n", ", ")

    # ─── Tri des champs par dépendances ──────────────────────────────────────

    # Sous-types qui dépendent d'un NIR présent dans la même ligne
    _NIR_DEPENDENTS = {
        "departementNaissance",
        "dateNaissance",
        "lieuNaissance",
        "civiliteNir",
        "prenomNir",
    }
    # Sous-types qui dépendent d'un codePostal présent dans la même ligne
    _CP_DEPENDENTS = {"ville", "adresseComplete"}

    @staticmethod
    def sort_fields_by_dependencies(fields: list) -> list:
        """
        Ordre de génération :
          1. Champs normaux
          2. Champ NIR  (s'il existe)
          3. Champs dépendants du NIR
          4. Champs codePostal
          5. Champs dépendants du codePostal (ville, adresse complète)
          6. Champs concat
        """

        nir_dep = DataGenerator._NIR_DEPENDENTS
        cp_dep = DataGenerator._CP_DEPENDENTS

        normal, nir_fields, nir_dependent, cp_fields, cp_dependent, concat = [], [], [], [], [], []

        for f in fields:
            sub = f.get("subType", "none") or "none"

            if sub == "concat":
                concat.append(f)
            elif sub == "nir":
                nir_fields.append(f)
            elif sub in nir_dep:
                nir_dependent.append(f)
            elif sub == "codePostal":
                cp_fields.append(f)
            elif sub in cp_dep:
                cp_dependent.append(f)
            else:
                normal.append(f)

        return normal + nir_fields + nir_dependent + cp_fields + cp_dependent + concat

    @staticmethod
    def inject_linked_field_ids(fields: list, fields_data: dict) -> None:
        """
        Pré-enregistre dans fields_data les identifiants des champs NIR et
        codePostal de la ligne, afin que les champs dépendants puissent les
        retrouver une fois générés.
        """
        for f in fields:
            sub = f.get("subType", "none") or "none"
            if sub == "nir":
                fields_data["_nir_field_id"] = f["id"]
            elif sub == "codePostal":
                fields_data["_cp_field_id"] = f["id"]

    # Alias de compatibilité
    @staticmethod
    def inject_nir_field_id(fields: list, fields_data: dict) -> None:
        DataGenerator.inject_linked_field_ids(fields, fields_data)


logger = logging.getLogger(__name__)
