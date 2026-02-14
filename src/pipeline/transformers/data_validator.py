"""
Module de validation des données météorologiques
Vérifie la cohérence et la qualité des données avant chargement dans MongoDB
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
from loguru import logger


class DataValidator:
    """
    Classe pour valider les données harmonisées
    """

    # Plages de valeurs acceptables pour chaque mesure
    VALID_RANGES = {
        "temperature": (-50, 60),  # °C
        "humidity": (0, 100),  # %
        "pressure": (900, 1100),  # hPa
        "dewpoint": (-60, 50),  # °C
        "wind_speed": (0, 250),  # km/h
        "wind_gust": (0, 400),  # km/h
        "wind_direction": (0, 360),  # degrés
        "precipitation_1h": (0, 300),  # mm
        "precipitation_3h": (0, 500),  # mm
        "precipitation_rate": (0, 500),  # mm/h
        "visibility": (0, 100000),  # m
        "cloud_cover": (0, 8),  # octas
        "snow_depth": (0, 1000),  # cm
        "uv_index": (0, 15),  # index
        "solar_radiation": (0, 1500)  # W/m²
    }

    def __init__(self, config: Dict):
        """
        Initialise le validateur avec la configuration

        Args:
            config: Configuration du pipeline
        """
        self.config = config
        self.strict_mode = config.get("validation", {}).get("strict_mode", False)

    def validate(self, record: Dict) -> Dict:
        """
        Valide un enregistrement harmonisé

        Args:
            record: Enregistrement à valider

        Returns:
            Dictionnaire avec résultat de validation
            {
                "is_valid": bool,
                "errors": List[str],
                "warnings": List[str]
            }
        """
        errors = []
        warnings = []

        # 1. Validation des champs obligatoires
        required_errors = self._validate_required_fields(record)
        errors.extend(required_errors)

        # 2. Validation du timestamp
        timestamp_errors, timestamp_warnings = self._validate_timestamp(record.get("timestamp"))
        errors.extend(timestamp_errors)
        warnings.extend(timestamp_warnings)

        # 3. Validation de la localisation
        location_errors = self._validate_location(
            record.get("station", {}).get("location", {})
        )
        errors.extend(location_errors)

        # 4. Validation des mesures
        measurements_warnings = self._validate_measurements(
            record.get("measurements", {})
        )
        warnings.extend(measurements_warnings)

        # 5. Calcul du score de complétude
        completeness_score = self._calculate_completeness(record)

        # Mettre à jour le record avec les résultats de validation
        if "data_quality" not in record:
            record["data_quality"] = {}

        record["data_quality"]["completeness_score"] = completeness_score
        record["data_quality"]["missing_fields"] = self._get_missing_fields(record)
        record["data_quality"]["validation_passed"] = len(errors) == 0
        record["data_quality"]["anomalies_detected"] = len(warnings) > 0

        # En mode strict, les warnings deviennent des erreurs
        if self.strict_mode and warnings:
            errors.extend(warnings)
            warnings = []

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }

    def _validate_required_fields(self, record: Dict) -> List[str]:
        """
        Valide la présence des champs obligatoires

        Args:
            record: Enregistrement à valider

        Returns:
            Liste d'erreurs
        """
        errors = []

        # Vérifier station
        station = record.get("station", {})
        if not station.get("id"):
            errors.append("Champ obligatoire manquant: station.id")
        if not station.get("name"):
            errors.append("Champ obligatoire manquant: station.name")
        if not station.get("network"):
            errors.append("Champ obligatoire manquant: station.network")

        # Vérifier location
        location = station.get("location", {})
        if location.get("latitude") is None:
            errors.append("Champ obligatoire manquant: station.location.latitude")
        if location.get("longitude") is None:
            errors.append("Champ obligatoire manquant: station.location.longitude")

        # Vérifier timestamp
        if not record.get("timestamp"):
            errors.append("Champ obligatoire manquant: timestamp")

        return errors

    def _validate_timestamp(self, timestamp: Any) -> tuple[List[str], List[str]]:
        """Valide le timestamp.

        Returns:
            (errors, warnings)
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not timestamp:
            return errors, warnings  # Déjà vérifié dans required_fields

        try:
            # Parser le timestamp
            dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
            if dt.tzinfo is None:
                # Assume UTC when tz is missing.
                dt = dt.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)

            # Vérifier qu'il n'est pas dans le futur
            if dt > now:
                errors.append(f"Timestamp dans le futur: {timestamp}")

            # ⚠️ MODIFICATION ICI : warning au lieu d'erreur
            one_year_ago = now - timedelta(days=365)
            if dt < one_year_ago:
                warnings.append(f"Timestamp ancien (> 1 an): {timestamp}")

        except Exception as e:
            errors.append(f"Timestamp invalide: {timestamp} ({str(e)})")

        return errors, warnings

    def _validate_location(self, location: Dict) -> List[str]:
        """
        Valide les coordonnées géographiques

        Args:
            location: Dictionnaire de localisation

        Returns:
            Liste d'erreurs
        """
        errors = []

        latitude = location.get("latitude")
        longitude = location.get("longitude")

        # Vérifier latitude
        if latitude is not None:
            if not (-90 <= latitude <= 90):
                errors.append(f"Latitude hors limites: {latitude} (doit être entre -90 et 90)")

        # Vérifier longitude
        if longitude is not None:
            if not (-180 <= longitude <= 180):
                errors.append(f"Longitude hors limites: {longitude} (doit être entre -180 et 180)")

        # Vérifier élévation
        elevation = location.get("elevation")
        if elevation is not None:
            if not (-500 <= elevation <= 9000):
                errors.append(f"Élévation improbable: {elevation}m")

        return errors

    def _validate_measurements(self, measurements: Dict) -> List[str]:
        """
        Valide les mesures météorologiques

        Args:
            measurements: Dictionnaire des mesures

        Returns:
            Liste de warnings
        """
        warnings = []

        for measurement_name, measurement_obj in measurements.items():
            if not isinstance(measurement_obj, dict):
                continue

            value = measurement_obj.get("value")

            # Ignorer les valeurs None
            if value is None:
                continue

            # Vérifier si la mesure a une plage de validation
            if measurement_name in self.VALID_RANGES:
                min_val, max_val = self.VALID_RANGES[measurement_name]

                if not (min_val <= value <= max_val):
                    warnings.append(
                        f"{measurement_name} hors plage normale: {value} "
                        f"(attendu entre {min_val} et {max_val})"
                    )

        # Vérifications de cohérence

        # Point de rosée <= température
        temp = measurements.get("temperature", {}).get("value")
        dewpoint = measurements.get("dewpoint", {}).get("value")
        if temp is not None and dewpoint is not None:
            if dewpoint > temp:
                warnings.append(
                    f"Point de rosée ({dewpoint}°C) > température ({temp}°C)"
                )

        # Rafales >= vent moyen
        wind_speed = measurements.get("wind_speed", {}).get("value")
        wind_gust = measurements.get("wind_gust", {}).get("value")
        if wind_speed is not None and wind_gust is not None:
            if wind_gust < wind_speed:
                warnings.append(
                    f"Rafales ({wind_gust} km/h) < vent moyen ({wind_speed} km/h)"
                )

        return warnings

    def _calculate_completeness(self, record: Dict) -> float:
        """
        Calcule le score de complétude des données (0 à 1)

        Args:
            record: Enregistrement à évaluer

        Returns:
            Score de complétude (0.0 à 1.0)
        """
        measurements = record.get("measurements", {})

        # Compter les mesures non-nulles
        total_fields = 0
        filled_fields = 0

        for measurement_obj in measurements.values():
            if isinstance(measurement_obj, dict):
                total_fields += 1
                if measurement_obj.get("value") is not None:
                    filled_fields += 1

        if total_fields == 0:
            return 0.0

        return round(filled_fields / total_fields, 3)

    def _get_missing_fields(self, record: Dict) -> List[str]:
        """
        Récupère la liste des champs manquants

        Args:
            record: Enregistrement à analyser

        Returns:
            Liste des noms de champs manquants
        """
        missing = []
        measurements = record.get("measurements", {})

        for measurement_name, measurement_obj in measurements.items():
            if isinstance(measurement_obj, dict):
                if measurement_obj.get("value") is None:
                    missing.append(measurement_name)

        return missing
