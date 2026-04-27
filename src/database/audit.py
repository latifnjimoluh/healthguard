"""
Module d'audit trail pour HealthGuard IA.
Implémente une chaîne de hash ininterrompue (structure blockchain légère)
pour garantir la non-répudiation des actions médicales.
"""

import uuid
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional


# Hash initial de la chaîne (genesis block)
GENESIS_HASH = "0" * 64


def compute_log_hash(log_entry: dict) -> str:
    """
    Calcule le hash SHA-256 d'une entrée de log pour la chaîne d'intégrité.

    Args:
        log_entry: Dictionnaire représentant l'entrée de log

    Returns:
        Hash SHA-256 en hexadécimal
    """
    # Sérialisation déterministe pour hashing cohérent
    log_str = json.dumps(log_entry, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(log_str.encode('utf-8')).hexdigest()


def log_action(
    user_id: str,
    action_type: str,
    table_cible: Optional[str],
    entite_id: Optional[str],
    db_connection
) -> str:
    """
    Enregistre une action dans l'audit trail avec chaînage de hash.

    Chaque log inclut le hash du log précédent, créant une chaîne
    ininterrompue. Toute falsification cassera la chaîne.

    Args:
        user_id: Identifiant de l'agent de santé
        action_type: Type d'action (LOGIN, CONSULTATION, DIAGNOSTIC, etc.)
        table_cible: Table concernée par l'action
        entite_id: ID de l'entité concernée
        db_connection: Connexion SQLite active

    Returns:
        ID du log créé
    """
    cursor = db_connection.cursor()

    # Récupération du hash du dernier log pour enchaînement
    cursor.execute(
        "SELECT hash_payload, hash_precedent, id_log, timestamp FROM audit_log "
        "ORDER BY timestamp DESC LIMIT 1"
    )
    last_log = cursor.fetchone()

    if last_log:
        # Hash du log précédent = hash calculé sur ses données
        previous_entry = {
            "id_log": last_log[2],
            "timestamp": last_log[3],
            "hash_payload": last_log[0],
            "hash_precedent": last_log[1]
        }
        hash_precedent = compute_log_hash(previous_entry)
    else:
        # Premier log de la chaîne
        hash_precedent = GENESIS_HASH

    # Création du nouvel entrée de log
    log_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Contenu du payload (ce qui sera hashé)
    payload = {
        "user_id": user_id,
        "action_type": action_type,
        "table_cible": table_cible,
        "entite_id": entite_id,
        "timestamp": timestamp
    }
    hash_payload = compute_log_hash(payload)

    # Insertion dans la base de données
    cursor.execute(
        """INSERT INTO audit_log
           (id_log, user_id, action_type, table_cible, entite_id,
            timestamp, hash_payload, hash_precedent)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (log_id, user_id, action_type, table_cible, entite_id,
         timestamp, hash_payload, hash_precedent)
    )
    db_connection.commit()

    return log_id


def verify_chain_integrity(db_connection) -> dict:
    """
    Vérifie l'intégrité complète de la chaîne d'audit trail.

    Parcourt tous les logs et vérifie que chaque hash_precedent
    correspond bien au hash calculé du log précédent.

    Args:
        db_connection: Connexion SQLite active

    Returns:
        dict: {
            "valid": bool,
            "total_logs": int,
            "first_broken_at": Optional[str] (ID du premier log cassé),
            "message": str
        }
    """
    cursor = db_connection.cursor()
    cursor.execute(
        "SELECT id_log, user_id, action_type, table_cible, entite_id, "
        "timestamp, hash_payload, hash_precedent FROM audit_log "
        "ORDER BY timestamp ASC"
    )
    logs = cursor.fetchall()

    if not logs:
        return {
            "valid": True,
            "total_logs": 0,
            "first_broken_at": None,
            "message": "Chaîne vide — aucun log à vérifier"
        }

    previous_hash = GENESIS_HASH

    for i, log in enumerate(logs):
        log_id, user_id, action_type, table_cible, entite_id, timestamp, \
            hash_payload, hash_precedent = log

        # Vérification que le hash_precedent correspond au log précédent
        if hash_precedent != previous_hash and i > 0:
            return {
                "valid": False,
                "total_logs": len(logs),
                "first_broken_at": log_id,
                "message": f"Chaîne cassée au log {log_id} — falsification détectée"
            }

        # Vérification du hash_payload
        payload = {
            "user_id": user_id,
            "action_type": action_type,
            "table_cible": table_cible,
            "entite_id": entite_id,
            "timestamp": timestamp
        }
        expected_hash = compute_log_hash(payload)
        if hash_payload != expected_hash:
            return {
                "valid": False,
                "total_logs": len(logs),
                "first_broken_at": log_id,
                "message": f"Hash payload invalide au log {log_id} — données falsifiées"
            }

        # Calcul du hash de ce log pour la vérification du suivant
        current_entry = {
            "id_log": log_id,
            "timestamp": timestamp,
            "hash_payload": hash_payload,
            "hash_precedent": hash_precedent
        }
        previous_hash = compute_log_hash(current_entry)

    return {
        "valid": True,
        "total_logs": len(logs),
        "first_broken_at": None,
        "message": f"Chaîne intègre — {len(logs)} logs vérifiés avec succès"
    }
