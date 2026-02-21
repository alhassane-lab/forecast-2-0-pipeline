"""
Loader pour charger les données dans MongoDB
"""

import os
from typing import List, Dict, Any
import re

import certifi
from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError, DuplicateKeyError
from loguru import logger


class MongoDBLoader:
    """
    Classe pour charger les données dans MongoDB
    """

    def __init__(self, config: Dict, dry_run: bool = False):
        """
        Initialise le loader MongoDB

        Args:
            config: Configuration contenant les informations MongoDB
            dry_run: Si True, simule l'écriture sans l'effectuer
        """
        self.config = config
        self.dry_run = dry_run

        # Base de données et collection
        # Prefer env overrides to simplify Docker/CI usage.
        db_name = (
            os.getenv("MONGODB_DATABASE")
            or config.get("mongodb", {}).get("database")
            or "forecast_2_0"
        )
        collection_name = (
            os.getenv("MONGODB_COLLECTION")
            or config.get("mongodb", {}).get("collection")
            or "weather_measurements"
        )

        self.client = None
        self.db = None
        self.collection = None

        if not dry_run:
            mongodb_uri = os.getenv('MONGODB_URI')
            if not mongodb_uri:
                raise ValueError("Variable d'environnement MONGODB_URI non définie")

            # Let PyMongo parse TLS settings from the URI by default.
            # Only override when explicitly requested via env vars.
            client_kwargs: Dict[str, Any] = {}

            tls_env = os.getenv("MONGODB_TLS")
            if tls_env is not None and tls_env != "":
                tls_norm = tls_env.strip().lower()
                if tls_norm in {"1", "true", "yes", "y"}:
                    client_kwargs["tls"] = True
                elif tls_norm in {"0", "false", "no", "n"}:
                    client_kwargs["tls"] = False

            allow_invalid = os.getenv("MONGODB_TLS_ALLOW_INVALID_CERTS", "").strip().lower()
            if allow_invalid in {"1", "true", "yes", "y"}:
                client_kwargs["tlsAllowInvalidCertificates"] = True

            # Ensure a CA bundle is available (notably in slim Docker images).
            # Apply only when TLS is expected.
            tls_expected = (
                mongodb_uri.startswith("mongodb+srv://")
                or bool(re.search(r"(?i)([?&](tls|ssl)=true)\\b", mongodb_uri))
                or client_kwargs.get("tls") is True
            )
            if tls_expected and "tlsCAFile" not in client_kwargs:
                client_kwargs["tlsCAFile"] = certifi.where()

            self.client = MongoClient(mongodb_uri, **client_kwargs)
            self.db = self.client[db_name]
            self.collection = self.db[collection_name]

        # Créer les index si nécessaire
        if not dry_run and self.collection is not None:
            self._ensure_indexes()

        logger.info(f"MongoDB Loader initialisé - DB: {db_name}, Collection: {collection_name}")
        if dry_run:
            logger.warning("Mode DRY-RUN: aucune donnée ne sera écrite")

    def _ensure_indexes(self):
        """
        Crée les index nécessaires dans MongoDB
        """
        self._remove_duplicate_records()
        try:
            # Index unique pour station+timestamp (force les doublons à l'insertion)
            self.collection.create_index(
                [
                    ("station.id", ASCENDING),
                    ("timestamp", ASCENDING)
                ],
                name="station_timestamp_unique_idx",
                unique=True,
                background=True
            )

            # Index pour recherches par réseau
            self.collection.create_index([
                ("station.network", ASCENDING),
                ("timestamp", ASCENDING)
            ], name="network_timestamp_idx")

            # Index géospatial
            self.collection.create_index([
                ("station.location_geo", "2dsphere")
            ], name="location_geo_idx")

            logger.info("✓ Index MongoDB créés/vérifiés")

        except Exception as e:
            logger.warning(f"Erreur lors de la création des index: {e}")

    def _remove_duplicate_records(self) -> int:
        """Supprime les doublons basés sur station.id + timestamp avant l'ajout de l'index unique."""
        if self.collection is None:
            return 0

        pipeline = [
            {
                "$group": {
                    "_id": {
                        "station_id": "$station.id",
                        "timestamp": "$timestamp"
                    },
                    "ids": {"$push": "$_id"},
                    "count": {"$sum": 1}
                }
            },
            {"$match": {"count": {"$gt": 1}}}
        ]

        duplicates = 0
        for doc in self.collection.aggregate(pipeline):
            ids_to_remove = doc["ids"][1:]
            if ids_to_remove:
                result = self.collection.delete_many({"_id": {"$in": ids_to_remove}})
                duplicates += result.deleted_count

        if duplicates:
            logger.warning(f"{duplicates} doublons supprimés avant création de l'index unique")
        return duplicates

    def bulk_insert_with_stats(self, records: List[Dict]) -> Dict[str, int]:
        """Insere en masse et retourne des stats detaillees."""
        total = len(records)
        result = {
            "input_records": total,
            "inserted_records": 0,
            "duplicates_ignored": 0,
            "failed_records": 0,
        }

        if not records:
            logger.warning("Aucune donnée à charger dans MongoDB")
            return result

        if self.dry_run:
            logger.info(f"[DRY-RUN] {total} enregistrements auraient été insérés")
            result["inserted_records"] = total
            return result

        if self.collection is None:
            raise RuntimeError("Collection MongoDB non initialisée")

        logger.info(f"Insertion de {total} enregistrements dans MongoDB...")

        try:
            inserted = len(self.collection.insert_many(records, ordered=False).inserted_ids)
            result["inserted_records"] = inserted
            logger.success(f"✓ {inserted} enregistrements insérés dans MongoDB")
            return result

        except BulkWriteError as e:
            details = e.details or {}
            inserted = int(details.get("nInserted", 0))
            write_errors = details.get("writeErrors", []) or []
            duplicates = sum(1 for err in write_errors if err.get("code") == 11000)
            failed = max(0, len(write_errors) - duplicates)

            result["inserted_records"] = inserted
            result["duplicates_ignored"] = duplicates
            result["failed_records"] = failed

            logger.warning(
                "Insertion partielle: "
                f"{inserted} insérés, {duplicates} doublons ignorés, {failed} erreurs"
            )
            return result

        except Exception as e:
            logger.error(f"Erreur lors de l'insertion dans MongoDB: {e}")
            raise

    def bulk_insert(self, records: List[Dict]) -> int:
        """
        Insère des enregistrements en masse dans MongoDB

        Args:
            records: Liste d'enregistrements à insérer

        Returns:
            Nombre d'enregistrements insérés
        """
        return self.bulk_insert_with_stats(records)["inserted_records"]

    def upsert_records_with_stats(self, records: List[Dict]) -> Dict[str, int]:
        """Effectue des upserts et retourne des stats detaillees."""
        total = len(records)
        result = {
            "input_records": total,
            "upserted_records": 0,
            "failed_records": 0,
        }

        if not records:
            return result

        if self.dry_run:
            logger.info(f"[DRY-RUN] {total} enregistrements auraient été upsertés")
            result["upserted_records"] = total
            return result

        if self.collection is None:
            raise RuntimeError("Collection MongoDB non initialisée")

        logger.info(f"Upsert de {total} enregistrements...")
        for record in records:
            try:
                filter_query = {
                    "station.id": record["station"]["id"],
                    "timestamp": record["timestamp"]
                }
                self.collection.update_one(
                    filter_query,
                    {"$set": record},
                    upsert=True
                )
                result["upserted_records"] += 1
            except Exception as e:
                result["failed_records"] += 1
                logger.warning(f"Erreur upsert: {e}")

        logger.success(
            f"✓ {result['upserted_records']} enregistrements upsertés "
            f"({result['failed_records']} erreurs)"
        )
        return result

    def upsert_records(self, records: List[Dict]) -> int:
        """
        Insère ou met à jour des enregistrements (upsert)

        Args:
            records: Liste d'enregistrements

        Returns:
            Nombre d'enregistrements traités
        """
        return self.upsert_records_with_stats(records)["upserted_records"]

    def close(self):
        """Ferme la connexion MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Connexion MongoDB fermée")
