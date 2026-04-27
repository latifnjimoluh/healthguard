"""
Module de chiffrement AES-256-CBC pour HealthGuard IA.
Implémente la dérivation de clé PBKDF2 et le chiffrement des données patients.
La clé de chiffrement n'est JAMAIS stockée sur disque.
"""

import os
import base64
import hashlib
import hmac
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# Paramètres de sécurité conformes OWASP 2024
PBKDF2_ITERATIONS = 256_000      # 256 000 itérations (OWASP recommandation)
SALT_SIZE = 32                    # 256 bits de sel
KEY_SIZE = 32                     # AES-256 = 32 bytes
IV_SIZE = 16                      # AES block size = 16 bytes
HMAC_SIZE = 32                    # HMAC-SHA256 = 32 bytes


def generate_salt() -> bytes:
    """Génère un sel aléatoire de 32 bytes pour PBKDF2."""
    return os.urandom(SALT_SIZE)


def generate_key(pin: str, salt: bytes) -> bytes:
    """
    Dérive une clé AES-256 depuis le PIN utilisateur via PBKDF2-SHA256.

    Args:
        pin: Code PIN de l'utilisateur (6+ chiffres)
        salt: Sel aléatoire de 32 bytes

    Returns:
        Clé AES-256 de 32 bytes (ne jamais stocker sur disque)
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(pin.encode('utf-8'))


def encrypt_data(data: str, key: bytes) -> bytes:
    """
    Chiffre des données avec AES-256-CBC + HMAC-SHA256 pour intégrité.

    Format de sortie : IV (16 bytes) + HMAC (32 bytes) + données chiffrées

    Args:
        data: Données en clair à chiffrer
        key: Clé AES-256 de 32 bytes

    Returns:
        Bytes chiffrés (IV + HMAC + ciphertext)
    """
    # Génération d'un IV aléatoire pour chaque chiffrement
    iv = os.urandom(IV_SIZE)

    # Chiffrement AES-256-CBC avec padding PKCS7
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data.encode('utf-8')) + padder.finalize()

    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    # Calcul HMAC-SHA256 pour vérification d'intégrité
    hmac_value = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()

    return iv + hmac_value + ciphertext


def decrypt_data(data: bytes, key: bytes) -> str:
    """
    Déchiffre des données AES-256-CBC avec vérification HMAC.

    Args:
        data: Bytes chiffrés (IV + HMAC + ciphertext)
        key: Clé AES-256 de 32 bytes

    Returns:
        Données déchiffrées en clair

    Raises:
        ValueError: Si la vérification HMAC échoue (intégrité compromise)
    """
    if len(data) < IV_SIZE + HMAC_SIZE + 16:
        raise ValueError("Données chiffrées trop courtes ou corrompues")

    # Extraction des composants
    iv = data[:IV_SIZE]
    stored_hmac = data[IV_SIZE:IV_SIZE + HMAC_SIZE]
    ciphertext = data[IV_SIZE + HMAC_SIZE:]

    # Vérification HMAC avant déchiffrement (protection contre attaques padding)
    expected_hmac = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(stored_hmac, expected_hmac):
        raise ValueError("Vérification HMAC échouée — données potentiellement falsifiées")

    # Déchiffrement AES-256-CBC
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()

    # Suppression du padding PKCS7
    unpadder = padding.PKCS7(128).unpadder()
    plain_data = unpadder.update(padded_data) + unpadder.finalize()

    return plain_data.decode('utf-8')


def encrypt_field(value: str, key: bytes) -> str:
    """
    Chiffre un champ individuel et retourne une chaîne base64.
    Utilisé pour chiffrer les champs sensibles stockés en SQLite.

    Args:
        value: Valeur du champ à chiffrer
        key: Clé AES-256 de 32 bytes

    Returns:
        Chaîne base64 représentant les données chiffrées
    """
    encrypted_bytes = encrypt_data(value, key)
    return base64.b64encode(encrypted_bytes).decode('utf-8')


def decrypt_field(encrypted_value: str, key: bytes) -> str:
    """
    Déchiffre un champ base64 chiffré.

    Args:
        encrypted_value: Chaîne base64 chiffrée
        key: Clé AES-256 de 32 bytes

    Returns:
        Valeur déchiffrée en clair
    """
    encrypted_bytes = base64.b64decode(encrypted_value.encode('utf-8'))
    return decrypt_data(encrypted_bytes, key)


def hash_data(data: str) -> str:
    """
    Calcule le hash SHA-256 d'une chaîne (utilisé pour l'audit trail).

    Args:
        data: Données à hasher

    Returns:
        Hash SHA-256 en hexadécimal
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()
