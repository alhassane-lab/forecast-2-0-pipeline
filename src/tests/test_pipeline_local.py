"""Smoke test local du pipeline sans appel reseau.

Ce test valide le chainage extraction locale -> harmonisation -> validation.
"""

import json
from pathlib import Path

from pipeline.extractors.infoclimat_extractor import InfoClimatExtractor
from pipeline.transformers.data_harmonizer import DataHarmonizer
from pipeline.transformers.data_validator import DataValidator


def test_local_pipeline_smoke(tmp_path: Path):
    config = {
        "validation": {"strict_mode": False},
    }

    sample_payload = {
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
                    "visibilite": "15000",
                }
            ]
        },
        "metadata": {
            "temperature": "temperature,degC",
            "humidite": "relative humidity,%",
        },
    }

    sample_file = tmp_path / "infoclimat_local.json"
    sample_file.write_text(json.dumps(sample_payload), encoding="utf-8")

    extractor = InfoClimatExtractor(config)
    harmonizer = DataHarmonizer(config)
    validator = DataValidator(config)

    raw_records = extractor.extract_from_local(str(sample_file))
    assert len(raw_records) == 1

    harmonized = harmonizer.harmonize_infoclimat(raw_records[0])
    result = validator.validate(harmonized)

    assert result["is_valid"] is True
    assert "station" in harmonized
    assert "measurements" in harmonized
    assert harmonized["data_quality"]["completeness_score"] is not None
