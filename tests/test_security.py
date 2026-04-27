"""
Tests unitaires — Module Sécurité HealthGuard IA.
Couvre : PIN auth, chiffrement AES, audit trail, verrouillage.
"""

import time
import pytest
from src.security.pin_auth import (
    hash_pin, verify_pin, check_pin_complexity,
    record_failed_attempt, reset_attempts, is_locked, _failed_attempts
)
from src.security.aes_cipher import AESCipher
from src.database.encryption import generate_key, generate_salt
from src.database.audit import log_action, verify_chain_integrity
from src.database.schema import get_in_memory_db


class TestPINAuth:
    """Tests de l'authentification PIN."""

    def setup_method(self):
        """Nettoyage des tentatives avant chaque test."""
        _failed_attempts.clear()

    def test_hash_pin_creates_non_reversible_hash(self):
        """Le hash PIN est non réversible."""
        pin = "246810"
        h = hash_pin(pin)
        assert pin not in h
        assert len(h) > 20

    def test_hash_pin_unique_salt(self):
        """Deux hashes du même PIN sont différents (sel unique)."""
        h1 = hash_pin("246810")
        h2 = hash_pin("246810")
        assert h1 != h2, "Chaque hash doit utiliser un sel unique"

    def test_verify_pin_correct(self):
        """PIN correct vérifié avec succès."""
        pin = "246810"
        h = hash_pin(pin)
        assert verify_pin(pin, h) is True

    def test_verify_pin_incorrect(self):
        """PIN incorrect retourne False."""
        h = hash_pin("246810")
        assert verify_pin("111111", h) is False

    def test_pin_complexity_valid(self):
        """PINs complexes acceptés."""
        assert check_pin_complexity("246810") is True
        assert check_pin_complexity("829374") is True
        assert check_pin_complexity("193847") is True

    def test_pin_complexity_too_short(self):
        """PIN < 6 chiffres rejeté."""
        assert check_pin_complexity("1234") is False

    def test_pin_complexity_sequence_ascending(self):
        """Séquence croissante rejetée."""
        assert check_pin_complexity("123456") is False
        assert check_pin_complexity("234567") is False

    def test_pin_complexity_sequence_descending(self):
        """Séquence décroissante rejetée."""
        assert check_pin_complexity("654321") is False

    def test_pin_complexity_repetition(self):
        """Répétition rejetée."""
        assert check_pin_complexity("111111") is False
        assert check_pin_complexity("000000") is False

    def test_lockout_after_5_attempts(self):
        """Verrouillage après 5 tentatives échouées."""
        user_id = "test_user_lockout"
        for i in range(5):
            record_failed_attempt(user_id)
        locked, seconds = is_locked(user_id)
        assert locked is True
        assert seconds > 0

    def test_no_lockout_before_5_attempts(self):
        """Pas de verrouillage avant 5 tentatives."""
        user_id = "test_user_nolockout"
        for i in range(4):
            record_failed_attempt(user_id)
        locked, _ = is_locked(user_id)
        assert locked is False

    def test_reset_attempts(self):
        """reset_attempts() efface le compteur."""
        user_id = "test_user_reset"
        for i in range(5):
            record_failed_attempt(user_id)
        reset_attempts(user_id)
        locked, _ = is_locked(user_id)
        assert locked is False


class TestAESCipher:
    """Tests du chiffrement AES-256-CBC."""

    def test_encrypt_decrypt_roundtrip(self):
        """Chiffrement / déchiffrement aller-retour."""
        salt = generate_salt()
        key = generate_key("246810", salt)
        cipher = AESCipher(key)
        original = "Données médicales confidentielles — HealthGuard IA"
        encrypted = cipher.encrypt(original)
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == original

    def test_different_ciphertext_each_call(self):
        """IV aléatoire → ciphertext différent à chaque appel."""
        salt = generate_salt()
        key = generate_key("246810", salt)
        cipher = AESCipher(key)
        data = "même données"
        enc1 = cipher.encrypt(data)
        enc2 = cipher.encrypt(data)
        assert enc1 != enc2

    def test_tampered_ciphertext_detected(self):
        """Modification du ciphertext détectée via HMAC."""
        salt = generate_salt()
        key = generate_key("246810", salt)
        cipher = AESCipher(key)
        encrypted = cipher.encrypt("données")
        import base64
        raw = bytearray(base64.b64decode(encrypted))
        raw[30] ^= 0xFF
        tampered_b64 = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(ValueError):
            cipher.decrypt(tampered_b64)

    def test_wrong_key_rejected(self):
        """Déchiffrement avec mauvaise clé échoue."""
        salt1 = generate_salt()
        salt2 = generate_salt()
        key1 = generate_key("246810", salt1)
        key2 = generate_key("987654", salt2)
        cipher1 = AESCipher(key1)
        cipher2 = AESCipher(key2)
        encrypted = cipher1.encrypt("données")
        with pytest.raises(ValueError):
            cipher2.decrypt(encrypted)

    def test_invalid_key_size_raises(self):
        """Clé de mauvaise taille lève ValueError."""
        with pytest.raises(ValueError):
            AESCipher(b"cle_trop_courte")


class TestPBKDF2Timing:
    """Tests de résistance brute force (timing)."""

    def test_key_derivation_time(self):
        """Derivation cle PBKDF2 > 50ms (resistance brute force — 256000 iterations)."""
        salt = generate_salt()
        start = time.time()
        generate_key("246810", salt)
        elapsed_ms = (time.time() - start) * 1000
        # Seuil 50ms : suffisant pour la resistance brute force avec 256000 iterations
        # (la valeur depend du CPU — un serveur rapide peut aller plus vite)
        assert elapsed_ms > 50, f"Derivation trop rapide : {elapsed_ms:.1f}ms — verifier iterations PBKDF2"


class TestAuditChainSecurity:
    """Tests sécurité de l'audit trail."""

    def test_falsification_detected(self):
        """Modification d'un log de la chaîne est détectée."""
        db = get_in_memory_db()
        import uuid
        for i in range(5):
            log_action("user_001", f"ACTION_{i}", "consultations", str(uuid.uuid4()), db)

        # Falsifier le hash_payload d'un log
        logs = db.execute("SELECT id_log FROM audit_log ORDER BY timestamp ASC").fetchall()
        target_id = logs[2]["id_log"]
        db.execute(
            "UPDATE audit_log SET hash_payload = 'hash_falsifie' WHERE id_log = ?",
            (target_id,)
        )
        db.commit()

        result = verify_chain_integrity(db)
        assert result["valid"] is False
        assert result["first_broken_at"] is not None

    def test_chain_complete_after_many_logs(self):
        """Chaîne intègre après 50 logs."""
        db = get_in_memory_db()
        import uuid
        for i in range(50):
            log_action("user_001", "CONSULTATION", "consultations", str(uuid.uuid4()), db)
        result = verify_chain_integrity(db)
        assert result["valid"] is True
        assert result["total_logs"] == 50
