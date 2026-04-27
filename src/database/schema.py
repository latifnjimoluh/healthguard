"""
Module de gestion de la base de données SQLite pour HealthGuard IA.
Crée et initialise la structure de la base de données locale.
"""

import sqlite3
import os
from pathlib import Path


# Chemin vers le schéma SQL
SCHEMA_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "schema.sql"
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "healthguard.db"


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """
    Crée et retourne une connexion à la base de données SQLite.

    Args:
        db_path: Chemin vers le fichier de base de données.
                 Utilise le chemin par défaut si non spécifié.

    Returns:
        Connexion SQLite active avec foreign keys activées
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    # Création du répertoire parent si nécessaire
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # Mode Write-Ahead Logging pour performance
    conn.row_factory = sqlite3.Row  # Accès aux colonnes par nom

    return conn


def initialize_database(db_path: str = None) -> sqlite3.Connection:
    """
    Initialise la base de données en appliquant le schéma SQL.

    Args:
        db_path: Chemin vers le fichier de base de données

    Returns:
        Connexion SQLite initialisée
    """
    conn = get_connection(db_path)

    # Lecture et exécution du schéma SQL
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    conn.executescript(schema_sql)
    conn.commit()

    return conn


def get_in_memory_db() -> sqlite3.Connection:
    """
    Crée une base de données en mémoire pour les tests unitaires.

    Returns:
        Connexion SQLite en mémoire initialisée avec le schéma complet
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    conn.executescript(schema_sql)
    conn.commit()

    return conn
