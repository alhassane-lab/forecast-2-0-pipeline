"""
Tests d'intégration pour le pipeline complet
"""

import pytest
import json
from datetime import datetime
from pathlib import Path
from pipeline.extractors.infoclimat_extractor import InfoClimatExtractor
from pipeline.transformers.data_harmonizer import DataHarmonizer
from pipeline.transformers.data_validator import DataValidator


class TestIntegrationPipeline:
    """Tests d'intégration du pipeline complet"""

    @pytest.fixture
    def config(self):
        """Configuration de test"""
        return {
            "s3": {
                "raw_bucket": "test-bucket",
                "processed_bucket": "test-processed"
            },
            "mongodb": {
                "database": "test_db",
                "collection": "test_collection"
            },
            "validation": {
                "strict_mode": False
            }
        }

    @pytest.fixture
    def sample_infoclimat_json(self, tmp_path):
        """Crée un fichier JSON InfoClimat temporaire pour les tests"""
        data = {
            "status": "OK",
            "stations": [],
            "metadata": {
                "temperature": "temperature,degC",
                "humidite": "relative humidity,%"
            },
            "hourly": {
                "07015": [
                    {
                        "id_station": "07015",
                        "dh_utc": "2024-10-05 14:00:00",
                        "temperature": "18.5",
                        "pression": "1015.3",
                        "humidite": "72",
                        "point_de_rosee": "13.2",
                        "vent_moyen": "10.0",
                        "vent_direction": "180",
                        "pluie_1h": "0",
                        "visibilite": "15000"
                    }
                ]
            }
        }

        file_path = tmp_path / "test_data.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        return file_path

    def test_full_pipeline_infoclimat(self, config, sample_infoclimat_json):
        """Test du pipeline complet pour données InfoClimat"""

        # 1. Extraction
        extractor = InfoClimatExtractor(config)
        records = extractor.extract_from_local(str(sample_infoclimat_json))

        assert len(records) > 0
        assert records[0]["source"] == "infoclimat"

        # 2. Transformation
        harmonizer = DataHarmonizer(config)
        harmonized_records = [
            harmonizer.harmonize_infoclimat(record) for record in records
        ]

        assert len(harmonized_records) == len(records)
        assert "station" in harmonized_records[0]
        assert "measurements" in harmonized_records[0]

        # 3. Validation
        validator = DataValidator(config)
        valid_records = []

        for record in harmonized_records:
            result = validator.validate(record)
            if result["is_valid"]:
                valid_records.append(record)

        assert len(valid_records) > 0

        # Vérifier la qualité
        for record in valid_records:
            quality = record.get("data_quality", {})
            assert quality.get("completeness_score") is not None
            assert quality.get("validation_passed") is True

    def test_data_structure_consistency(self, config, sample_infoclimat_json):
        """Vérifie la cohérence de la structure des données à travers le pipeline"""

        extractor = InfoClimatExtractor(config)
        harmonizer = DataHarmonizer(config)
        validator = DataValidator(config)

        # Pipeline complet
        raw_records = extractor.extract_from_local(str(sample_infoclimat_json))
        harmonized = harmonizer.harmonize_infoclimat(raw_records[0])
        validation_result = validator.validate(harmonized)

        # Vérifier que toutes les clés essentielles sont présentes
        required_keys = ["station", "timestamp", "measurements", "data_quality", "metadata"]
        for key in required_keys:
            assert key in harmonized, f"Clé manquante: {key}"

        # Vérifier la structure station
        station_keys = ["id", "name", "network", "location"]
        for key in station_keys:
            assert key in harmonized["station"], f"Clé station manquante: {key}"

        # Vérifier la structure location
        location_keys = ["latitude", "longitude"]
        for key in location_keys:
            assert key in harmonized["station"]["location"], f"Clé location manquante: {key}"
