"""
Module de contrôle qualité des données
Génère des rapports détaillés sur la qualité des données traitées
"""

from typing import Dict, List
from collections import defaultdict
from datetime import datetime
from loguru import logger


class QualityChecker:
    """
    Classe pour analyser la qualité des données et générer des rapports
    """

    def __init__(self):
        """Initialise le contrôleur qualité"""
        pass

    def generate_report(self, records: List[Dict], stats: Dict) -> Dict:
        """
        Génère un rapport de qualité complet

        Args:
            records: Liste des enregistrements validés
            stats: Statistiques d'exécution du pipeline

        Returns:
            Rapport de qualité structuré
        """
        logger.info("Génération du rapport de qualité...")

        if not records:
            return self._empty_report(stats)

        report = {
            "execution_info": {
                "start_time": stats.get("start_time"),
                "end_time": stats.get("end_time"),
                "duration_seconds": stats.get("duration_seconds"),
                "timestamp": datetime.utcnow().isoformat()
            },
            "summary": {
                "total_records_processed": stats.get("records_extracted", 0),
                "records_transformed": stats.get("records_transformed", 0),
                "records_validated": stats.get("records_validated", 0),
                "records_loaded": stats.get("records_loaded", 0),
                "records_rejected": stats.get("records_rejected", 0),
                "rejection_rate": self._calculate_rejection_rate(stats)
            },
            "by_station": self._analyze_by_station(records),
            "by_network": self._analyze_by_network(records),
            "field_completeness": self._analyze_field_completeness(records),
            "temporal_analysis": self._analyze_temporal_coverage(records),
            "data_quality_scores": self._analyze_quality_scores(records),
            "anomalies": self._detect_anomalies(records),
            "errors": stats.get("errors", [])
        }

        logger.success("✓ Rapport de qualité généré")

        return report

    def _empty_report(self, stats: Dict) -> Dict:
        """
        Génère un rapport vide quand aucune donnée n'est disponible

        Args:
            stats: Statistiques d'exécution

        Returns:
            Rapport vide
        """
        return {
            "execution_info": {
                "start_time": stats.get("start_time"),
                "end_time": stats.get("end_time"),
                "duration_seconds": stats.get("duration_seconds"),
                "timestamp": datetime.utcnow().isoformat()
            },
            "summary": {
                "total_records_processed": 0,
                "records_validated": 0,
                "records_loaded": 0,
                "records_rejected": 0
            },
            "message": "Aucune donnée à analyser",
            "errors": stats.get("errors", [])
        }

    def _calculate_rejection_rate(self, stats: Dict) -> float:
        """
        Calcule le taux de rejet

        Args:
            stats: Statistiques d'exécution

        Returns:
            Taux de rejet (0.0 à 1.0)
        """
        total = stats.get("records_extracted", 0)
        rejected = stats.get("records_rejected", 0)

        if total == 0:
            return 0.0

        return round(rejected / total, 4)

    def _analyze_by_station(self, records: List[Dict]) -> Dict:
        """
        Analyse les données par station

        Args:
            records: Liste d'enregistrements

        Returns:
            Statistiques par station
        """
        station_stats = defaultdict(lambda: {
            "network": None,
            "station_name": None,
            "records": 0,
            "completeness_scores": [],
            "anomalies": 0,
            "location": None
        })

        for record in records:
            station = record.get("station", {})
            station_id = station.get("id")

            if station_id:
                stats = station_stats[station_id]
                stats["network"] = station.get("network")
                stats["station_name"] = station.get("name")
                stats["records"] += 1
                stats["location"] = station.get("location")

                # Score de complétude
                quality = record.get("data_quality", {})
                score = quality.get("completeness_score")
                if score is not None:
                    stats["completeness_scores"].append(score)

                # Anomalies
                if quality.get("anomalies_detected"):
                    stats["anomalies"] += 1

        # Calculer les moyennes
        result = {}
        for station_id, stats in station_stats.items():
            scores = stats["completeness_scores"]
            avg_completeness = sum(scores) / len(scores) if scores else 0

            result[station_id] = {
                "network": stats["network"],
                "station_name": stats["station_name"],
                "records": stats["records"],
                "avg_completeness": round(avg_completeness, 3),
                "anomalies": stats["anomalies"],
                "location": stats["location"]
            }

        return result

    def _analyze_by_network(self, records: List[Dict]) -> Dict:
        """
        Analyse les données par réseau (InfoClimat, WeatherUnderground)

        Args:
            records: Liste d'enregistrements

        Returns:
            Statistiques par réseau
        """
        network_stats = defaultdict(lambda: {
            "records": 0,
            "stations": set(),
            "completeness_scores": []
        })

        for record in records:
            station = record.get("station", {})
            network = station.get("network")
            station_id = station.get("id")

            if network:
                stats = network_stats[network]
                stats["records"] += 1
                if station_id:
                    stats["stations"].add(station_id)

                quality = record.get("data_quality", {})
                score = quality.get("completeness_score")
                if score is not None:
                    stats["completeness_scores"].append(score)

        # Formater les résultats
        result = {}
        for network, stats in network_stats.items():
            scores = stats["completeness_scores"]
            avg_completeness = sum(scores) / len(scores) if scores else 0

            result[network] = {
                "records": stats["records"],
                "stations_count": len(stats["stations"]),
                "avg_completeness": round(avg_completeness, 3)
            }

        return result

    def _analyze_field_completeness(self, records: List[Dict]) -> Dict:
        """
        Analyse la complétude par champ de mesure

        Args:
            records: Liste d'enregistrements

        Returns:
            Taux de complétude par champ
        """
        field_stats = defaultdict(lambda: {"total": 0, "filled": 0})

        for record in records:
            measurements = record.get("measurements", {})

            for field_name, measurement in measurements.items():
                if isinstance(measurement, dict):
                    field_stats[field_name]["total"] += 1
                    if measurement.get("value") is not None:
                        field_stats[field_name]["filled"] += 1

        # Calculer les pourcentages
        result = {}
        for field_name, stats in field_stats.items():
            total = stats["total"]
            filled = stats["filled"]
            percentage = (filled / total) if total > 0 else 0

            result[field_name] = {
                "completeness": round(percentage, 3),
                "filled_count": filled,
                "total_count": total
            }

        return result

    def _analyze_temporal_coverage(self, records: List[Dict]) -> Dict:
        """
        Analyse la couverture temporelle des données

        Args:
            records: Liste d'enregistrements

        Returns:
            Statistiques temporelles
        """
        timestamps = []

        for record in records:
            ts = record.get("timestamp")
            if ts:
                try:
                    dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
                    timestamps.append(dt)
                except:
                    pass

        if not timestamps:
            return {
                "min_timestamp": None,
                "max_timestamp": None,
                "time_span_hours": 0,
                "records_count": 0
            }

        timestamps.sort()
        min_ts = timestamps[0]
        max_ts = timestamps[-1]
        time_span = (max_ts - min_ts).total_seconds() / 3600  # en heures

        return {
            "min_timestamp": min_ts.isoformat(),
            "max_timestamp": max_ts.isoformat(),
            "time_span_hours": round(time_span, 2),
            "records_count": len(timestamps)
        }

    def _analyze_quality_scores(self, records: List[Dict]) -> Dict:
        """
        Analyse les scores de qualité des enregistrements

        Args:
            records: Liste d'enregistrements

        Returns:
            Statistiques sur les scores de qualité
        """
        scores = []
        validation_passed = 0
        anomalies_detected = 0

        for record in records:
            quality = record.get("data_quality", {})

            score = quality.get("completeness_score")
            if score is not None:
                scores.append(score)

            if quality.get("validation_passed"):
                validation_passed += 1

            if quality.get("anomalies_detected"):
                anomalies_detected += 1

        if not scores:
            return {
                "avg_completeness": 0,
                "min_completeness": 0,
                "max_completeness": 0,
                "validation_passed": 0,
                "anomalies_detected": 0
            }

        return {
            "avg_completeness": round(sum(scores) / len(scores), 3),
            "min_completeness": round(min(scores), 3),
            "max_completeness": round(max(scores), 3),
            "validation_passed": validation_passed,
            "validation_passed_rate": round(validation_passed / len(records), 3),
            "anomalies_detected": anomalies_detected,
            "anomalies_rate": round(anomalies_detected / len(records), 3)
        }

    def _detect_anomalies(self, records: List[Dict]) -> List[Dict]:
        """
        Détecte et liste les anomalies dans les données

        Args:
            records: Liste d'enregistrements

        Returns:
            Liste des anomalies détectées
        """
        anomalies = []

        for i, record in enumerate(records):
            quality = record.get("data_quality", {})

            if quality.get("anomalies_detected"):
                station = record.get("station", {})

                anomaly = {
                    "record_index": i,
                    "station_id": station.get("id"),
                    "station_name": station.get("name"),
                    "timestamp": record.get("timestamp"),
                    "missing_fields": quality.get("missing_fields", []),
                    "completeness_score": quality.get("completeness_score")
                }

                anomalies.append(anomaly)

        # Limiter à 100 anomalies dans le rapport
        return anomalies[:100]
