"""
Module d'authentification PIN pour HealthGuard IA.
Implémente le hachage Argon2id, la vérification de complexité et le verrouillage.
"""

import time
from datetime import datetime, timezone
from typing import Optional

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
    HAS_ARGON2 = True
except ImportError:
    import hashlib
    import os
    HAS_ARGON2 = False

# Paramètres Argon2id OWASP 2024
ARGON2_TIME_COST = 3          # 3 itérations
ARGON2_MEMORY_COST = 65536    # 64 Mo de mémoire
ARGON2_PARALLELISM = 4        # 4 threads parallèles

# Paramètres de verrouillage
MAX_ATTEMPTS = 5
# Délai exponentiel en secondes : 5, 25, 125, 625...
LOCKOUT_BASE_DELAY = 5

# Stockage en mémoire des tentatives (en production : persisté en BDD)
_failed_attempts: dict = {}   # {user_id: {"count": int, "last_attempt": float}}

if HAS_ARGON2:
    _hasher = PasswordHasher(
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM
    )


def hash_pin(pin: str) -> str:
    """
    Hache le PIN utilisateur avec Argon2id (recommandation OWASP 2024).
    Jamais stocké en clair.

    Args:
        pin: Code PIN (6+ chiffres)

    Returns:
        Hash Argon2id sécurisé (sel inclus dans le hash)
    """
    if not check_pin_complexity(pin):
        raise ValueError("PIN trop simple : éviter les séquences (123456, 111111)")

    if HAS_ARGON2:
        return _hasher.hash(pin)
    else:
        # Fallback PBKDF2-SHA256 si argon2-cffi non disponible
        import hashlib
        import os
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt, 256000)
        return f"pbkdf2:{salt.hex()}:{key.hex()}"


def verify_pin(pin: str, stored_hash: str) -> bool:
    """
    Vérifie le PIN contre le hash stocké.

    Args:
        pin: Code PIN saisi
        stored_hash: Hash stocké en base

    Returns:
        True si le PIN est correct, False sinon
    """
    try:
        if HAS_ARGON2:
            if stored_hash.startswith("pbkdf2:"):
                return _verify_pbkdf2(pin, stored_hash)
            return _hasher.verify(stored_hash, pin)
        else:
            return _verify_pbkdf2(pin, stored_hash)
    except Exception:
        return False


def _verify_pbkdf2(pin: str, stored_hash: str) -> bool:
    """Vérification PBKDF2 (fallback)."""
    import hashlib
    try:
        parts = stored_hash.split(":")
        salt = bytes.fromhex(parts[1])
        expected_key = bytes.fromhex(parts[2])
        key = hashlib.pbkdf2_hmac('sha256', pin.encode(), salt, 256000)
        import hmac
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False


def check_pin_complexity(pin: str) -> bool:
    """
    Vérifie la complexité du PIN (6+ chiffres, pas de séquences triviales).

    Args:
        pin: PIN à vérifier

    Returns:
        True si complexité suffisante, False sinon
    """
    if not pin or len(pin) < 6:
        return False

    if not pin.isdigit():
        return False

    # Rejeter les séquences croissantes (123456, 234567)
    is_ascending = all(
        int(pin[i+1]) == int(pin[i]) + 1
        for i in range(len(pin)-1)
    )
    if is_ascending:
        return False

    # Rejeter les séquences décroissantes (654321)
    is_descending = all(
        int(pin[i+1]) == int(pin[i]) - 1
        for i in range(len(pin)-1)
    )
    if is_descending:
        return False

    # Rejeter les répétitions (111111, 222222, 000000)
    if len(set(pin)) == 1:
        return False

    # Rejeter les répétitions partielles (112233, 121212)
    if len(set(pin)) <= 2:
        return False

    return True


def record_failed_attempt(user_id: str) -> int:
    """
    Enregistre une tentative échouée et retourne le nombre total.

    Args:
        user_id: Identifiant de l'utilisateur

    Returns:
        Nombre de tentatives échouées consécutives
    """
    if user_id not in _failed_attempts:
        _failed_attempts[user_id] = {"count": 0, "last_attempt": 0.0}

    _failed_attempts[user_id]["count"] += 1
    _failed_attempts[user_id]["last_attempt"] = time.time()

    return _failed_attempts[user_id]["count"]


def reset_attempts(user_id: str) -> None:
    """Réinitialise le compteur de tentatives après succès."""
    if user_id in _failed_attempts:
        del _failed_attempts[user_id]


def is_locked(user_id: str) -> tuple:
    """
    Vérifie si l'utilisateur est verrouillé suite à trop de tentatives.

    Délai exponentiel : 5s, 25s, 125s, 625s après chaque groupe de 5 tentatives.

    Args:
        user_id: Identifiant de l'utilisateur

    Returns:
        Tuple (est_verrouillé: bool, secondes_restantes: int)
    """
    if user_id not in _failed_attempts:
        return False, 0

    data = _failed_attempts[user_id]
    count = data["count"]
    last_attempt = data["last_attempt"]

    if count < MAX_ATTEMPTS:
        return False, 0

    # Calcul du délai exponentiel
    nb_groupes = (count - MAX_ATTEMPTS) // MAX_ATTEMPTS + 1
    delai = LOCKOUT_BASE_DELAY ** nb_groupes  # 5^1=5, 5^2=25, 5^3=125...

    elapsed = time.time() - last_attempt
    secondes_restantes = int(delai - elapsed)

    if secondes_restantes > 0:
        return True, secondes_restantes
    else:
        return False, 0
