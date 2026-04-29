"""
Module de chiffrement AES-256-CBC pour HealthGuard IA.
Interface de haut niveau pour le chiffrement/déchiffrement des données patients.
"""

import os
import base64
import hashlib
import hmac as hmac_module
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

# Tailles en bytes
KEY_SIZE = 32      # AES-256
IV_SIZE = 16       # AES block size
HMAC_SIZE = 32     # HMAC-SHA256

# Importation du module de dérivation de clé
from src.database.encryption import generate_key, generate_salt


class AESCipher:
    """
    Classe de chiffrement AES-256-CBC avec HMAC-SHA256 intégré.

    Utilisation :
        cipher = AESCipher(key)
        encrypted = cipher.encrypt("données sensibles")
        decrypted = cipher.decrypt(encrypted)
    """

    def __init__(self, key: bytes):
        """
        Initialise le cipher avec une clé AES-256.

        Args:
            key: Clé de 32 bytes (dérivée via PBKDF2 depuis le PIN)
        """
        if len(key) != KEY_SIZE:
            raise ValueError(f"Clé AES-256 requise ({KEY_SIZE} bytes), reçu {len(key)} bytes")
        self._key = key

    def encrypt(self, plaintext: str) -> str:
        """
        Chiffre une chaîne de caractères.

        Format de sortie base64 : IV (16B) + HMAC-SHA256 (32B) + ciphertext

        Args:
            plaintext: Données en clair

        Returns:
            Données chiffrées encodées en base64
        """
        # Génération IV aléatoire par chiffrement
        iv = os.urandom(IV_SIZE)

        # Padding PKCS7 et chiffrement AES-256-CBC
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode('utf-8')) + padder.finalize()

        cipher = Cipher(
            algorithms.AES(self._key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()

        # HMAC-SHA256 pour intégrité (Encrypt-then-MAC)
        mac = hmac_module.new(self._key, iv + ciphertext, hashlib.sha256).digest()

        # Assemblage et encodage base64
        combined = iv + mac + ciphertext
        return base64.b64encode(combined).decode('utf-8')

    def decrypt(self, encrypted_b64: str) -> str:
        """
        Déchiffre des données chiffrées.

        Args:
            encrypted_b64: Données chiffrées en base64

        Returns:
            Données déchiffrées

        Raises:
            ValueError: Si le HMAC est invalide (intégrité compromise)
        """
        try:
            combined = base64.b64decode(encrypted_b64.encode('utf-8'))
        except Exception as e:
            raise ValueError(f"Données base64 invalides : {e}")

        if len(combined) < IV_SIZE + HMAC_SIZE + 16:
            raise ValueError("Données chiffrées corrompues ou trop courtes")

        # Extraction des composants
        iv = combined[:IV_SIZE]
        stored_mac = combined[IV_SIZE:IV_SIZE + HMAC_SIZE]
        ciphertext = combined[IV_SIZE + HMAC_SIZE:]

        # Vérification HMAC avant déchiffrement
        expected_mac = hmac_module.new(self._key, iv + ciphertext, hashlib.sha256).digest()
        if not hmac_module.compare_digest(stored_mac, expected_mac):
            raise ValueError("Vérification HMAC échouée  données potentiellement falsifiées")

        # Déchiffrement AES-256-CBC
        cipher = Cipher(
            algorithms.AES(self._key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Suppression padding PKCS7
        unpadder = padding.PKCS7(128).unpadder()
        plaintext_bytes = unpadder.update(padded_plaintext) + unpadder.finalize()

        return plaintext_bytes.decode('utf-8')

    @classmethod
    def from_pin(cls, pin: str, salt: bytes = None) -> tuple:
        """
        Crée un AESCipher depuis un PIN utilisateur.

        Args:
            pin: Code PIN (6+ chiffres)
            salt: Sel de 32 bytes (généré si None)

        Returns:
            Tuple (AESCipher, salt)  conserver le sel pour la dérivation future
        """
        if salt is None:
            salt = generate_salt()

        key = generate_key(pin, salt)
        return cls(key), salt
