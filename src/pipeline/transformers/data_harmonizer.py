"""
Module d'harmonisation des données météorologiques
Convertit les données de différentes sources vers un format unifié MongoDB
"""

from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
import re

class DataHarmonizer:
    """
    Classe pour harmoniser les données de différentes sources vers un schéma unifié
    """

    def __init__(self, config: Dict):
        """
        Initialise l'harmoniseur avec la configuration

        Args:
            config: Configuration du pipeline
        """
        self.config = config

    def harmonize_infoclimat(self, record: Dict) -> Dict:
        """
        Harmonise un enregistrement InfoClimat vers le schéma MongoDB

        Args:
            record: Enregistrement brut InfoClimat

        Returns:
            Enregistrement harmonisé
        """
        measurements = record.get("measurements", {})

        lat = self._to_float(record.get("latitude"))
        lon = self._to_float(record.get("longitude"))

        location = {
            "latitude": lat,
            "longitude": lon,
            "elevation": self._to_int(record.get("elevation")),
            "city": record.get("city"),
            "country": record.get("country"),
            "region": record.get("region"),
        }
        location_geo = {"type": "Point", "coordinates": [lon, lat]} if (lat is not None and lon is not None) else None

        # Construire l'enregistrement harmonisé
        harmonized = {
            "station": {
                "id": record.get("station_id"),
                "name": record.get("station_name"),
                "network": "InfoClimat",
                "type": record.get("station_type", "unknown"),
                "location": location,
                "location_geo": location_geo,
            },
            "timestamp": record.get("timestamp"),
            "measurements": {
                "temperature": self._create_measurement(
                    measurements.get("temperature"), "°C"
                ),
                "humidity": self._create_measurement(
                    measurements.get("humidite"), "%"
                ),
                "pressure": self._create_measurement(
                    measurements.get("pression"), "hPa"
                ),
                "dewpoint": self._create_measurement(
                    measurements.get("point_de_rosee"), "°C"
                ),
                "wind_speed": self._create_measurement(
                    measurements.get("vent_moyen"), "km/h"
                ),
                "wind_gust": self._create_measurement(
                    measurements.get("vent_rafales"), "km/h"
                ),
                "wind_direction": self._create_measurement(
                    measurements.get("vent_direction"), "degrees"
                ),
                "precipitation_1h": self._create_measurement(
                    measurements.get("pluie_1h"), "mm"
                ),
                "precipitation_3h": self._create_measurement(
                    measurements.get("pluie_3h"), "mm"
                ),
                "visibility": self._create_measurement(
                    measurements.get("visibilite"), "m"
                ),
                "cloud_cover": self._create_measurement(
                    measurements.get("nebulosite"), "octas"
                ),
                "snow_depth": self._create_measurement(
                    measurements.get("neige_au_sol"), "cm"
                ),
                "weather_code": self._create_measurement(
                    measurements.get("temps_omm"), "omm_code"
                )
            },
            "data_quality": {
                "completeness_score": None,  # Calculé plus tard
                "missing_fields": [],
                "validation_passed": None,
                "anomalies_detected": False
            },
            "metadata": {
                "source_file": f"infoclimat/{record.get('station_id')}",
                "ingestion_timestamp": datetime.utcnow().isoformat(),
                "pipeline_version": "1.0.0"
            }
        }

        return harmonized

    def harmonize_wunderground(self, record: Dict) -> Dict:
        """
        Harmonise un enregistrement Weather Underground vers le schéma MongoDB

        Args:
            record: Enregistrement brut Weather Underground

        Returns:
            Enregistrement harmonisé
        """
        measurements = record.get("measurements", {})

        lat = self._to_float(record.get("latitude"))
        lon = self._to_float(record.get("longitude"))

        location = {
            "latitude": lat,
            "longitude": lon,
            "elevation": self._to_int(record.get("elevation")),
            "city": record.get("city"),
            "country": record.get("country"),
            "region": record.get("region"),
        }
        location_geo = {"type": "Point", "coordinates": [lon, lat]} if (lat is not None and lon is not None) else None

        harmonized = {
            "station": {
                "id": record.get("station_id"),
                "name": record.get("station_name"),
                "network": "WeatherUnderground",
                "type": "amateur",
                "location": location,
                "location_geo": location_geo,
                "hardware": record.get("hardware"),
                "software": record.get("software")
            },
            "timestamp": self._parse_timestamp(record.get("timestamp")),
            "measurements": {
                "temperature": self._create_measurement(
                    measurements.get("temperature"), "°C"
                ),
                "humidity": self._create_measurement(
                    measurements.get("humidity"), "%"
                ),
                "pressure": self._create_measurement(
                    measurements.get("pressure"), "hPa"
                ),
                "dewpoint": self._create_measurement(
                    measurements.get("dewpoint"), "°C"
                ),
                "wind_speed": self._create_measurement(
                    measurements.get("wind_speed"), "km/h"
                ),
                "wind_gust": self._create_measurement(
                    measurements.get("wind_gust"), "km/h"
                ),
                "wind_direction": measurements.get("wind_direction"),
                "precipitation_rate": self._create_measurement(
                    measurements.get("precip_rate"), "mm/h"
                ),
                "precipitation_accumulated": self._create_measurement(
                    measurements.get("precip_accum"), "mm"
                ),
                "uv_index": self._create_measurement(
                    measurements.get("uv_index"), "index"
                ),
                "solar_radiation": self._create_measurement(
                    measurements.get("solar_radiation"), "W/m²"
                )
            },
            "data_quality": {
                "completeness_score": None,
                "missing_fields": [],
                "validation_passed": None,
                "anomalies_detected": False
            },
            "metadata": {
                "source_file": f"wunderground/{record.get('station_id')}",
                "ingestion_timestamp": datetime.utcnow().isoformat(),
                "pipeline_version": "1.0.0"
            }
        }

        return harmonized

    def _create_measurement(self, value: Any, unit: str) -> Dict:
        """
        Crée un objet measurement avec valeur et unité

        Args:
            value: Valeur de la mesure
            unit: Unité de mesure

        Returns:
            Dictionnaire avec value et unit
        """
        # Convertir la valeur
        if value is None or value == "" or str(value).upper() in ["N/A", "NULL", "NONE"]:
            converted_value = None
        else:
            # Essayer de convertir en float
            try:
                converted_value = float(value)
            except (ValueError, TypeError):
                converted_value = None

        return {
            "value": converted_value,
            "unit": unit
        }

    from typing import Any, Optional
    from datetime import datetime
    import re

    def _parse_timestamp(self, timestamp: Any, file_date: Optional[str] = None) -> Optional[str]:
        if timestamp is None:
            return None

        ts_str = str(timestamp).strip().replace("\xa0", " ")

        # 👉 NOUVEAU : format US avec AM/PM
        am_pm_formats = [
            "%m/%d/%y %I:%M %p",
            "%m/%d/%y %I:%M:%S %p",
        ]
        for fmt in am_pm_formats:
            try:
                dt = datetime.strptime(ts_str, fmt)
                return dt.isoformat()
            except ValueError:
                pass

        # Cas heure seule, combiner avec la date du fichier
        if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", ts_str) and file_date:
            ts_str = f"{file_date} {ts_str}"

        ts_str = ts_str.replace(" ", "T")

        # Formats standards
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(ts_str, fmt)
                return dt.isoformat()
            except ValueError:
                continue

        # fallback ISO
        try:
            dt = datetime.fromisoformat(ts_str)
            return dt.isoformat()
        except Exception:
            return None

    def _to_float(self, value: Any) -> Optional[float]:
        """
        Convertit une valeur en float

        Args:
            value: Valeur à convertir

        Returns:
            Float ou None
        """
        if value is None or value == "":
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _to_int(self, value: Any) -> Optional[int]:
        """
        Convertit une valeur en int

        Args:
            value: Valeur à convertir

        Returns:
            Int ou None
        """
        if value is None or value == "":
            return None

        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
