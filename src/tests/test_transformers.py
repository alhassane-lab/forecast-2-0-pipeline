"""
Tests unitaires pour les transformateurs de données
"""

import pytest
from datetime import datetime
from pipeline.transformers.data_harmonizer import DataHarmonizer
from pipeline.transformers.data_validator import DataValidator


class TestDataHarmonizer:
    """Tests pour le module d'harmonisation"""

    @pytest.fixture
    def harmonizer(self):
        """Fixture pour créer un harmonizer"""
        config = {}
        return DataHarmonizer(config)

    @pytest.fixture
    def sample_infoclimat_record(self):
        """Fixture avec un enregistrement InfoClimat exemple"""
        return {
            "source": "infoclimat",
            "station_id": "07015",
            "station_name": "Lille-Lesquin",
            "station_type": "synop",
            "latitude": 50.575,
            "longitude": 3.092,
            "elevation": 47,
            "city": "Lille",
            "country": "France",
            "region": "Hauts-de-France",
            "timestamp": "2024-10-05 14:00:00",
            "measurements": {
                "temperature": "15.5",
                "pression": "1013.2",
                "humidite": "75",
                "point_de_rosee": "11.2",
                "vent_moyen": "12.5",
                "vent_rafales": "18.0",
                "vent_direction": "270",
                "pluie_1h": "0",
                "pluie_3h": "0.5",
                "visibilite": "10000",
                "nebulosite": "5",
                "neige_au_sol": None
            }
        }

    def test_harmonize_infoclimat_basic(self, harmonizer, sample_infoclimat_record):
        """Test de l'harmonisation basique InfoClimat"""
        result = harmonizer.harmonize_infoclimat(sample_infoclimat_record)

        # Vérifier la structure
        assert "station" in result
        assert "timestamp" in result
        assert "measurements" in result
        assert "data_quality" in result
        assert "metadata" in result

        # Vérifier les données station
        assert result["station"]["id"] == "07015"
        assert result["station"]["name"] == "Lille-Lesquin"
        assert result["station"]["network"] == "InfoClimat"

        # Vérifier la localisation
        assert result["station"]["location"]["latitude"] == 50.575
        assert result["station"]["location"]["longitude"] == 3.092
        assert result["station"]["location"]["elevation"] == 47

    def test_harmonize_measurements_conversion(self, harmonizer, sample_infoclimat_record):
        """Test de la conversion des mesures"""
        result = harmonizer.harmonize_infoclimat(sample_infoclimat_record)

        measurements = result["measurements"]

        # Vérifier que les strings sont convertis en float
        assert measurements["temperature"]["value"] == 15.5
        assert measurements["temperature"]["unit"] == "°C"

        assert measurements["humidity"]["value"] == 75
        assert measurements["humidity"]["unit"] == "%"

        assert measurements["pressure"]["value"] == 1013.2
        assert measurements["pressure"]["unit"] == "hPa"

    def test_harmonize_null_values(self, harmonizer, sample_infoclimat_record):
        """Test de la gestion des valeurs nulles"""
        sample_infoclimat_record["measurements"]["nebulosite"] = ""
        sample_infoclimat_record["measurements"]["neige_au_sol"] = None

        result = harmonizer.harmonize_infoclimat(sample_infoclimat_record)

        measurements = result["measurements"]
        assert measurements["cloud_cover"]["value"] is None
        assert measurements["snow_depth"]["value"] is None


class TestDataValidator:
    """Tests pour le module de validation"""

    @pytest.fixture
    def validator(self):
        """Fixture pour créer un validator"""
        config = {"validation": {"strict_mode": False}}
        return DataValidator(config)

    @pytest.fixture
    def valid_record(self):
        """Fixture avec un enregistrement valide"""
        return {
            "station": {
                "id": "ILAMAD25",
                "name": "La Madeleine",
                "network": "WeatherUnderground",
                "location": {
                    "latitude": 50.659,
                    "longitude": 3.07,
                    "elevation": 23
                }
            },
            "timestamp": "2024-10-05T14:30:00",
            "measurements": {
                "temperature": {"value": 18.5, "unit": "°C"},
                "humidity": {"value": 72, "unit": "%"},
                "pressure": {"value": 1015.3, "unit": "hPa"}
            },
            "data_quality": {},
            "metadata": {}
        }

    def test_validate_valid_record(self, validator, valid_record):
        """Test de validation d'un enregistrement valide"""
        result = validator.validate(valid_record)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_missing_required_field(self, validator, valid_record):
        """Test de validation avec champ obligatoire manquant"""
        del valid_record["station"]["id"]

        result = validator.validate(valid_record)

        assert result["is_valid"] is False
        assert any("station.id" in error for error in result["errors"])

    def test_validate_invalid_coordinates(self, validator, valid_record):
        """Test de validation avec coordonnées invalides"""
        valid_record["station"]["location"]["latitude"] = 95.0  # > 90

        result = validator.validate(valid_record)

        assert result["is_valid"] is False
        assert any("Latitude" in error for error in result["errors"])

    def test_validate_out_of_range_temperature(self, validator, valid_record):
        """Test de validation avec température hors plage"""
        valid_record["measurements"]["temperature"]["value"] = 75.0  # > 60

        result = validator.validate(valid_record)

        # Devrait être un warning, pas une erreur
        assert result["is_valid"] is True
        assert any("temperature" in warning for warning in result["warnings"])

    def test_validate_dewpoint_greater_than_temp(self, validator, valid_record):
        """Test de cohérence: point de rosée > température"""
        valid_record["measurements"]["temperature"] = {"value": 15.0, "unit": "°C"}
        valid_record["measurements"]["dewpoint"] = {"value": 20.0, "unit": "°C"}

        result = validator.validate(valid_record)

        assert any("Point de rosée" in warning for warning in result["warnings"])

    def test_calculate_completeness(self, validator, valid_record):
        """Test du calcul du score de complétude"""
        result = validator.validate(valid_record)

        # Devrait avoir un score de complétude
        completeness = valid_record["data_quality"]["completeness_score"]
        assert 0.0 <= completeness <= 1.0
