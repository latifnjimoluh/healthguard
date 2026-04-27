"""
Module d'inférence ML pour HealthGuard IA.
Charge le modèle entraîné et effectue des prédictions sur de nouveaux cas.
"""

import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "ml" / "model_xgboost.pkl"
FEATURE_NAMES_PATH = Path(__file__).parent.parent.parent / "data" / "ml" / "feature_names.json"

# Instance globale du modèle (chargée une seule fois)
_model_cache = None


@dataclass
class ProbabilitesDiagnostic:
    """Résultat de l'inférence ML avec probabilités par classe."""
    probabilites: dict              # {maladie: probabilité}
    top_1_diagnostic: str
    top_1_probabilite: float
    top_2_diagnostic: Optional[str]
    top_2_probabilite: float
    features_utilisees: list = field(default_factory=list)
    features_manquantes: list = field(default_factory=list)


def load_model() -> dict:
    """
    Charge le modèle ML depuis le disque (avec cache en mémoire).

    Returns:
        dict avec 'model', 'label_encoder', 'feature_names'

    Raises:
        FileNotFoundError: Si le modèle n'a pas encore été entraîné
    """
    global _model_cache

    if _model_cache is not None:
        return _model_cache

    if not MODEL_PATH.exists():
        # Modèle absent — entraîner automatiquement
        print("Modèle absent — entraînement automatique en cours...")
        from src.ml.train_model import train_model, save_model
        results = train_model()
        save_model(results)

    with open(MODEL_PATH, 'rb') as f:
        _model_cache = pickle.load(f)

    return _model_cache


def _prepare_input(symptomes: dict, feature_names: list) -> np.ndarray:
    """
    Prépare le vecteur d'entrée pour l'inférence.

    Gère les features manquantes (SpO2 optionnel → médiane).

    Args:
        symptomes: Dictionnaire de symptômes
        feature_names: Liste ordonnée des features attendues

    Returns:
        Array numpy de shape (1, n_features)
    """
    # Valeurs par défaut pour les features manquantes
    defaults = {
        "fievre": 0, "toux": 0, "diarrhee": 0, "vomissements": 0,
        "cephalee": 0, "frissons": 0, "courbatures": 0, "dyspnee": 0,
        "hemoptysie": 0, "oedemes": 0, "convulsions": 0, "trouble_conscience": 0,
        "temperature_celsius": 37.0,
        "age_ans": 30.0,
        "poids_kg": 60.0,
        "frequence_respiratoire": 18.0,
        "spo2_percent": 97.0,   # Valeur normale par défaut si non mesuré
        "duree_symptomes_jours": 3.0,
        "saison_pluie": 0, "zone_endemie_tb": 0,
        "contact_tb_connu": 0, "epidemie_cholera_active": 0,
        "sexe": 0, "grossesse": 0
    }

    values = []
    for feature in feature_names:
        if feature in symptomes and symptomes[feature] is not None:
            values.append(float(symptomes[feature]))
        else:
            values.append(defaults.get(feature, 0.0))

    return np.array(values).reshape(1, -1)


def predict(symptomes: dict) -> ProbabilitesDiagnostic:
    """
    Prédit le diagnostic à partir des symptômes fournis.

    Args:
        symptomes: Dictionnaire des symptômes et mesures
                   Features optionnelles : spo2_percent (si oxymètre non disponible)

    Returns:
        ProbabilitesDiagnostic avec probabilités par classe et top diagnostics
    """
    model_data = load_model()
    model = model_data["model"]
    le = model_data["label_encoder"]
    feature_names = model_data["feature_names"]

    # Identification des features manquantes
    features_manquantes = [f for f in feature_names if f not in symptomes or symptomes[f] is None]

    # Préparation du vecteur d'entrée
    X = _prepare_input(symptomes, feature_names)

    # Inférence
    probas_array = model.predict_proba(X)[0]

    # Construction du dictionnaire de probabilités
    probabilites = {
        le.classes_[i]: float(probas_array[i])
        for i in range(len(le.classes_))
    }

    # Top 2 diagnostics
    sorted_diags = sorted(probabilites.items(), key=lambda x: x[1], reverse=True)
    top_1_diag, top_1_prob = sorted_diags[0]
    top_2_diag, top_2_prob = sorted_diags[1] if len(sorted_diags) > 1 else (None, 0.0)

    return ProbabilitesDiagnostic(
        probabilites=probabilites,
        top_1_diagnostic=top_1_diag,
        top_1_probabilite=top_1_prob,
        top_2_diagnostic=top_2_diag if top_2_prob > 0.20 else None,
        top_2_probabilite=top_2_prob,
        features_utilisees=[f for f in feature_names if f not in features_manquantes],
        features_manquantes=features_manquantes
    )


def predict_batch(symptomes_list: list) -> list:
    """
    Prédit les diagnostics pour une liste de cas.

    Args:
        symptomes_list: Liste de dictionnaires de symptômes

    Returns:
        Liste de ProbabilitesDiagnostic
    """
    return [predict(s) for s in symptomes_list]
