"""
Module de synchronisation offline pour HealthGuard IA.
Gère la queue de synchronisation et la transmission sécurisée vers le serveur district.
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Optional
from src.database.encryption import encrypt_field, decrypt_field


def add_to_sync_queue(
    table_cible: str,
    operation: str,
    payload: dict,
    key: bytes,
    db_connection
) -> str:
    """
    Ajoute un enregistrement à la queue de synchronisation.

    Args:
        table_cible: Nom de la table concernée
        operation: Type d'opération (INSERT, UPDATE, DELETE)
        payload: Données à synchroniser (seront chiffrées)
        key: Clé AES-256 pour chiffrement du payload
        db_connection: Connexion SQLite active

    Returns:
        ID de l'entrée dans la queue
    """
    queue_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Chiffrement du payload avant stockage
    payload_json = json.dumps(payload, ensure_ascii=False)
    payload_chiffre = encrypt_field(payload_json, key)

    cursor = db_connection.cursor()
    cursor.execute(
        """INSERT INTO sync_queue
           (id_queue, table_cible, operation, payload_chiffre, tentatives,
            derniere_tentative, created_at)
           VALUES (?, ?, ?, ?, 0, NULL, ?)""",
        (queue_id, table_cible, operation, payload_chiffre, timestamp)
    )
    db_connection.commit()

    return queue_id


def get_pending_sync_items(db_connection, max_tentatives: int = 3) -> list:
    """
    Récupère les éléments en attente de synchronisation.

    Args:
        db_connection: Connexion SQLite active
        max_tentatives: Nombre maximum de tentatives avant abandon

    Returns:
        Liste des éléments en attente
    """
    cursor = db_connection.cursor()
    cursor.execute(
        """SELECT id_queue, table_cible, operation, payload_chiffre,
                  tentatives, derniere_tentative
           FROM sync_queue
           WHERE tentatives < ?
           ORDER BY created_at ASC""",
        (max_tentatives,)
    )
    return cursor.fetchall()


def get_sync_status(db_connection) -> dict:
    """
    Retourne le statut de la queue de synchronisation.

    Returns:
        dict avec compteurs et horodatages
    """
    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM sync_queue WHERE tentatives < 3")
    pending_count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT MAX(derniere_tentative) FROM sync_queue WHERE derniere_tentative IS NOT NULL"
    )
    last_sync = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM consultations WHERE statut_sync = 'SYNCED'")
    synced_count = cursor.fetchone()[0]

    return {
        "pending_sync_count": pending_count,
        "last_sync": last_sync,
        "synced_count": synced_count
    }


def mark_synced(queue_id: str, db_connection) -> None:
    """
    Marque un élément comme synchronisé et le supprime de la queue.

    Args:
        queue_id: ID de l'entrée dans la queue
        db_connection: Connexion SQLite active
    """
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM sync_queue WHERE id_queue = ?", (queue_id,))
    db_connection.commit()


def increment_tentative(queue_id: str, db_connection) -> None:
    """
    Incrémente le compteur de tentatives d'un élément de la queue.

    Args:
        queue_id: ID de l'entrée dans la queue
        db_connection: Connexion SQLite active
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    cursor = db_connection.cursor()
    cursor.execute(
        """UPDATE sync_queue
           SET tentatives = tentatives + 1, derniere_tentative = ?
           WHERE id_queue = ?""",
        (timestamp, queue_id)
    )
    db_connection.commit()
