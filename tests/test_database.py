"""
Tests unitaires  Module Base de Données HealthGuard IA.
Couvre : création BDD, chiffrement, audit trail.
"""

import pytest
import uuid
from src.database.schema import get_in_memory_db
from src.database.encryption import (
    generate_key, generate_salt, encrypt_data, decrypt_data,
    encrypt_field, decrypt_field, hash_data
)
from src.database.audit import log_action, verify_chain_integrity, compute_log_hash


class TestEncryption:
    """Tests du module de chiffrement AES-256-CBC."""

    def test_generate_key_deterministic(self):
        """Une même clé est générée pour même PIN + sel."""
        salt = generate_salt()
        key1 = generate_key("123456", salt)
        key2 = generate_key("123456", salt)
        assert key1 == key2, "PBKDF2 doit être déterministe pour même PIN+sel"

    def test_generate_key_different_pins(self):
        """Des PINs différents génèrent des clés différentes."""
        salt = generate_salt()
        key1 = generate_key("123456", salt)
        key2 = generate_key("654321", salt)
        assert key1 != key2

    def test_generate_key_different_salts(self):
        """Un même PIN avec des sels différents donne des clés différentes."""
        salt1 = generate_salt()
        salt2 = generate_salt()
        key1 = generate_key("123456", salt1)
        key2 = generate_key("123456", salt2)
        assert key1 != key2

    def test_encrypt_decrypt_roundtrip(self):
        """Chiffrement puis déchiffrement donne les données originales."""
        salt = generate_salt()
        key = generate_key("123456", salt)
        original = "Données patient confidentielles  Test HealthGuard"
        encrypted = encrypt_data(original, key)
        decrypted = decrypt_data(encrypted, key)
        assert decrypted == original

    def test_encrypt_different_iv_each_time(self):
        """Chaque chiffrement génère un IV différent (sécurité sémantique)."""
        salt = generate_salt()
        key = generate_key("123456", salt)
        data = "test données"
        enc1 = encrypt_data(data, key)
        enc2 = encrypt_data(data, key)
        assert enc1 != enc2, "IV doit être aléatoire  ciphertexts doivent être différents"

    def test_decrypt_with_wrong_key_fails(self):
        """Déchiffrement avec mauvaise clé lève ValueError."""
        salt1 = generate_salt()
        salt2 = generate_salt()
        key1 = generate_key("123456", salt1)
        key2 = generate_key("789012", salt2)
        data = "données secrètes"
        encrypted = encrypt_data(data, key1)
        with pytest.raises(ValueError):
            decrypt_data(encrypted, key2)

    def test_encrypt_field_base64(self):
        """encrypt_field retourne une chaîne base64 valide."""
        import base64
        salt = generate_salt()
        key = generate_key("123456", salt)
        encrypted = encrypt_field("nom du patient", key)
        # Vérifier que c'est du base64 valide
        decoded = base64.b64decode(encrypted.encode())
        assert len(decoded) > 0

    def test_encrypt_decrypt_field_roundtrip(self):
        """encrypt_field / decrypt_field aller-retour."""
        salt = generate_salt()
        key = generate_key("123456", salt)
        original = "Aminatou Wali"
        encrypted = encrypt_field(original, key)
        decrypted = decrypt_field(encrypted, key)
        assert decrypted == original

    def test_tampered_data_detected(self):
        """Falsification des données chiffrées est détectée via HMAC."""
        salt = generate_salt()
        key = generate_key("123456", salt)
        data = "données importantes"
        encrypted = encrypt_data(data, key)
        # Modifier un byte au milieu du ciphertext
        tampered = bytearray(encrypted)
        tampered[25] ^= 0xFF
        with pytest.raises(ValueError):
            decrypt_data(bytes(tampered), key)

    def test_hash_data_sha256(self):
        """hash_data produit un hash SHA-256 de 64 caractères hex."""
        h = hash_data("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_data_deterministic(self):
        """hash_data est déterministe."""
        assert hash_data("test") == hash_data("test")


class TestDatabase:
    """Tests de la base de données SQLite."""

    def test_database_creation(self):
        """Base de données créée avec les 7 tables requises."""
        db = get_in_memory_db()
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        required_tables = {
            "patients", "consultations", "diagnostics", "traitements",
            "audit_log", "sync_queue", "ref_maladies"
        }
        assert required_tables.issubset(table_names)

    def test_ref_maladies_populated(self):
        """Table ref_maladies contient les 6 maladies cibles."""
        db = get_in_memory_db()
        count = db.execute("SELECT COUNT(*) FROM ref_maladies").fetchone()[0]
        assert count >= 5, f"Attendu >= 5 maladies, trouvé {count}"

    def test_insert_and_retrieve_patient(self):
        """Insertion et récupération d'un patient chiffré."""
        import json
        from datetime import datetime, timezone
        db = get_in_memory_db()
        salt = generate_salt()
        key = generate_key("123456", salt)

        patient_id = str(uuid.uuid4())
        nom_chiffre = encrypt_field("Aminatou Wali", key)
        timestamp = datetime.now(timezone.utc).isoformat()

        db.execute(
            """INSERT INTO patients
               (id_patient, nom_chiffre, sexe, village_code, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (patient_id, nom_chiffre, "F", "NGD_001", timestamp, timestamp)
        )
        db.commit()

        patient = db.execute(
            "SELECT * FROM patients WHERE id_patient = ?", (patient_id,)
        ).fetchone()

        assert patient is not None
        nom_dechiffre = decrypt_field(patient["nom_chiffre"], key)
        assert nom_dechiffre == "Aminatou Wali"


class TestAuditTrail:
    """Tests de la chaîne d'audit trail."""

    def test_log_action_creates_entry(self):
        """log_action crée une entrée dans audit_log."""
        db = get_in_memory_db()
        log_id = log_action("user_001", "LOGIN", None, None, db)
        assert log_id is not None
        entry = db.execute(
            "SELECT * FROM audit_log WHERE id_log = ?", (log_id,)
        ).fetchone()
        assert entry is not None
        assert entry["action_type"] == "LOGIN"

    def test_chain_genesis_hash(self):
        """Premier log a le hash genesis (64 zéros)."""
        db = get_in_memory_db()
        log_action("user_001", "FIRST_ACTION", None, None, db)
        entry = db.execute(
            "SELECT hash_precedent FROM audit_log ORDER BY timestamp ASC LIMIT 1"
        ).fetchone()
        assert entry["hash_precedent"] == "0" * 64

    def test_chain_integrity_empty_db(self):
        """Vérification chaîne sur BDD vide retourne True."""
        db = get_in_memory_db()
        result = verify_chain_integrity(db)
        assert result["valid"] is True

    def test_chain_integrity_valid(self):
        """Chaîne de plusieurs logs est intègre."""
        db = get_in_memory_db()
        for i in range(5):
            log_action(f"user_{i}", f"ACTION_{i}", "consultations", str(uuid.uuid4()), db)
        result = verify_chain_integrity(db)
        assert result["valid"] is True
        assert result["total_logs"] == 5

    def test_chain_integrity_after_tampering(self):
        """Falsification d'un log casse la chaîne."""
        db = get_in_memory_db()
        for i in range(3):
            log_action("user_001", f"ACTION_{i}", "consultations", str(uuid.uuid4()), db)

        # Falsifier le hash_payload du 2ème log
        logs = db.execute(
            "SELECT id_log FROM audit_log ORDER BY timestamp ASC"
        ).fetchall()
        second_log_id = logs[1]["id_log"]

        db.execute(
            "UPDATE audit_log SET hash_payload = ? WHERE id_log = ?",
            ("hash_falsiie_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", second_log_id)
        )
        db.commit()

        result = verify_chain_integrity(db)
        assert result["valid"] is False, "La chaîne doit être détectée comme corrompue"
        assert result["first_broken_at"] is not None
