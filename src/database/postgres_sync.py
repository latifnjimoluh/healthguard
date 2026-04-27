"""
Module de synchronisation vers PostgreSQL (serveur district).
Envoie les données en attente depuis SQLite local vers la BD PostgreSQL centrale.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

from src.database.encryption import decrypt_field

load_dotenv(Path(__file__).parent.parent.parent / ".env")


def get_pg_connection():
    """Retourne une connexion PostgreSQL depuis les variables d'environnement."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", "healthguard"),
        connect_timeout=5
    )


def sync_to_postgres(sqlite_conn, encryption_key: bytes) -> dict:
    """
    Synchronise les données en attente de SQLite vers PostgreSQL.

    Args:
        sqlite_conn: Connexion SQLite locale
        encryption_key: Clé AES-256 pour déchiffrer les données

    Returns:
        dict {success, synced_patients, synced_consultations, errors}
    """
    result = {
        "success": False,
        "synced_patients": 0,
        "synced_consultations": 0,
        "errors": []
    }

    try:
        pg = get_pg_connection()
        pg_cur = pg.cursor()
    except Exception as e:
        result["errors"].append(f"Connexion PostgreSQL impossible : {e}")
        return result

    try:
        # --- 1. Synchroniser les patients ---
        patients_pending = sqlite_conn.execute(
            "SELECT * FROM patients WHERE updated_at > COALESCE((SELECT MAX(updated_at) FROM patients WHERE id_patient = 'SYNC_MARKER'), '1970-01-01')"
        ).fetchall()

        # Plus simple : sync tous les patients non encore envoyés
        # On utilise sync_queue pour cibler uniquement les nouveaux
        queue_items = sqlite_conn.execute(
            """SELECT id_queue, table_cible, operation, payload_chiffre
               FROM sync_queue WHERE tentatives < 3
               ORDER BY created_at ASC"""
        ).fetchall()

        for item in queue_items:
            id_queue = item[0]
            table = item[1]
            operation = item[2]
            payload_chiffre = item[3]

            try:
                # Déchiffrement du payload
                payload_json = decrypt_field(payload_chiffre, encryption_key)
                payload = json.loads(payload_json)

                if table == "patients":
                    _upsert_patient(pg_cur, payload)
                    result["synced_patients"] += 1

                elif table == "consultations":
                    _upsert_consultation(pg_cur, payload, sqlite_conn)
                    result["synced_consultations"] += 1

                # Marquer comme traité dans SQLite
                sqlite_conn.execute(
                    "DELETE FROM sync_queue WHERE id_queue = ?", (id_queue,)
                )
                sqlite_conn.execute(
                    "UPDATE consultations SET statut_sync = 'SYNCED' WHERE id_consultation = ?",
                    (payload.get("id_consultation", ""),)
                )

            except Exception as e:
                # Incrémenter tentatives en cas d'erreur sur cet item
                sqlite_conn.execute(
                    "UPDATE sync_queue SET tentatives = tentatives + 1, derniere_tentative = ? WHERE id_queue = ?",
                    (datetime.now(timezone.utc).isoformat(), id_queue)
                )
                result["errors"].append(f"Item {id_queue} ({table}) : {e}")

        pg.commit()
        sqlite_conn.commit()

        # Enregistrer dans sync_log PostgreSQL
        _log_sync(pg_cur, result)
        pg.commit()

        result["success"] = True

    except Exception as e:
        result["errors"].append(f"Erreur sync globale : {e}")
        pg.rollback()
    finally:
        pg_cur.close()
        pg.close()

    return result


def _upsert_patient(pg_cur, payload: dict):
    """Insère ou met à jour un patient dans PostgreSQL."""
    pg_cur.execute(
        """INSERT INTO patients
           (id_patient, nom_chiffre, date_naissance, sexe, village_code, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id_patient) DO UPDATE SET
               nom_chiffre = EXCLUDED.nom_chiffre,
               updated_at  = EXCLUDED.updated_at""",
        (
            payload.get("id_patient"),
            payload.get("nom_chiffre", ""),
            payload.get("date_naissance"),
            payload.get("sexe"),
            payload.get("village_code"),
            payload.get("created_at"),
            payload.get("updated_at"),
        )
    )


def _upsert_consultation(pg_cur, payload: dict, sqlite_conn):
    """Insère ou met à jour une consultation + son diagnostic dans PostgreSQL."""
    # S'assurer que le patient existe en PG (insert minimal si absent)
    id_patient = payload.get("id_patient")
    if id_patient:
        pg_cur.execute(
            """INSERT INTO patients (id_patient, nom_chiffre)
               VALUES (%s, %s)
               ON CONFLICT (id_patient) DO NOTHING""",
            (id_patient, "[chiffre]")
        )

    # Insérer la consultation
    pg_cur.execute(
        """INSERT INTO consultations
           (id_consultation, id_patient, date_heure, agent_id, symptomes_json, statut_sync, created_at)
           VALUES (%s, %s, %s, %s, %s, 'SYNCED', %s)
           ON CONFLICT (id_consultation) DO NOTHING""",
        (
            payload.get("id_consultation"),
            payload.get("id_patient"),
            payload.get("date_heure"),
            payload.get("agent_id"),
            payload.get("symptomes_json", ""),
            payload.get("created_at"),
        )
    )

    # Insérer le diagnostic associé si présent
    diag = payload.get("diagnostic")
    if diag:
        pg_cur.execute(
            """INSERT INTO diagnostics
               (id_diagnostic, id_consultation, maladie_code, probabilite_ml,
                decision_arbre, recommandation_json, gravite_score, couleur_alerte, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (id_diagnostic) DO NOTHING""",
            (
                diag.get("id_diagnostic"),
                payload.get("id_consultation"),
                diag.get("maladie_code"),
                diag.get("probabilite_ml"),
                diag.get("decision_arbre"),
                diag.get("recommandation_json", ""),
                diag.get("gravite_score"),
                diag.get("couleur_alerte"),
                diag.get("created_at"),
            )
        )


def _log_sync(pg_cur, result: dict):
    """Enregistre le résultat de la sync dans sync_log."""
    pg_cur.execute(
        """INSERT INTO sync_log
           (nb_consultations, nb_patients, statut, message)
           VALUES (%s, %s, %s, %s)""",
        (
            result["synced_consultations"],
            result["synced_patients"],
            "SUCCESS" if result["success"] and not result["errors"] else "PARTIAL",
            "; ".join(result["errors"]) if result["errors"] else "OK"
        )
    )


def test_pg_connection() -> bool:
    """Vérifie que PostgreSQL est accessible."""
    try:
        conn = get_pg_connection()
        conn.close()
        return True
    except Exception:
        return False
