"""
Entraînement du modèle XGBoost pour HealthGuard IA.
Entraîne un classifieur multi-classes sur les 6 maladies cibles.
Critère de succès : sensibilité paludisme_grave >= 85%, tuberculose >= 80%.
"""

import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.impute import SimpleImputer

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    HAS_XGB = False

from src.ml.data_generator import generate_dataset, get_feature_names, OUTPUT_PATH

# Chemins de sortie
MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "ml" / "model_xgboost.pkl"
FEATURE_NAMES_PATH = Path(__file__).parent.parent.parent / "data" / "ml" / "feature_names.json"
ENCODER_PATH = Path(__file__).parent.parent.parent / "data" / "ml" / "label_encoder.pkl"


def load_or_generate_dataset() -> pd.DataFrame:
    """Charge le dataset CSV ou le génère si absent."""
    if OUTPUT_PATH.exists():
        return pd.read_csv(OUTPUT_PATH)
    else:
        print("Dataset non trouvé  génération en cours...")
        df = generate_dataset()
        df.to_csv(OUTPUT_PATH, index=False)
        return df


def prepare_features(df: pd.DataFrame) -> tuple:
    """
    Prépare les features et labels pour l'entraînement.

    Gère les valeurs manquantes (SpO2 optionnel) par imputation médiane.

    Returns:
        Tuple (X, y, feature_names, label_encoder)
    """
    feature_names = get_feature_names()

    # Vérification des colonnes disponibles
    available_features = [f for f in feature_names if f in df.columns]
    missing_features = [f for f in feature_names if f not in df.columns]

    if missing_features:
        print(f"Features manquantes (créées avec 0) : {missing_features}")
        for f in missing_features:
            df[f] = 0

    X = df[feature_names].copy()
    y_raw = df["label"]

    # Encodage des labels
    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    # Imputation des valeurs manquantes (SpO2 notamment)
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)
    X = pd.DataFrame(X_imputed, columns=feature_names)

    return X, y, feature_names, le


def train_model(df: pd.DataFrame = None) -> dict:
    """
    Entraîne le modèle XGBoost et évalue ses performances.

    Args:
        df: DataFrame de données. Si None, charge ou génère le dataset.

    Returns:
        dict avec modèle, métriques et informations
    """
    if df is None:
        df = load_or_generate_dataset()

    print(f"Dataset chargé : {len(df)} cas, {len(df.columns)} colonnes")

    X, y, feature_names, le = prepare_features(df)

    # Split train/val/test : 70/15/15
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )

    print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    # Calcul des poids de classe pour équilibrage
    classes, counts = np.unique(y_train, return_counts=True)
    class_weights = {int(cls): len(y_train) / (len(classes) * count)
                     for cls, count in zip(classes, counts)}

    sample_weights_train = np.array([class_weights[label] for label in y_train])

    if HAS_XGB:
        print("Entraînement XGBoost...")
        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=-1
        )
        model.fit(
            X_train, y_train,
            sample_weight=sample_weights_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
    else:
        print("XGBoost non disponible  utilisation RandomForest...")
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            random_state=42,
            n_jobs=-1,
            class_weight="balanced"
        )
        model.fit(X_train, y_train, sample_weight=sample_weights_train)

    # Évaluation sur le set de test
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    # Rapport de classification
    class_names = le.classes_
    report = classification_report(
        y_test, y_pred,
        target_names=class_names,
        output_dict=True
    )

    print("\n=== RAPPORT DE CLASSIFICATION ===")
    print(classification_report(y_test, y_pred, target_names=class_names))

    # Vérification des critères critiques
    palu_grave_idx = list(le.classes_).index("paludisme_grave")
    tb_idx = list(le.classes_).index("tuberculose")

    sensibilite_palu_grave = report["paludisme_grave"]["recall"]
    sensibilite_tb = report["tuberculose"]["recall"]

    print(f"\n=== CRITERES DE SUCCES ===")
    print(f"Sensibilite paludisme grave : {sensibilite_palu_grave:.1%} (cible >= 85%)")
    print(f"Sensibilite tuberculose     : {sensibilite_tb:.1%} (cible >= 80%)")

    success_palu = sensibilite_palu_grave >= 0.85
    success_tb = sensibilite_tb >= 0.80

    print(f"Paludisme grave : {'VALIDE' if success_palu else 'ECHOUE'}")
    print(f"Tuberculose     : {'VALIDE' if success_tb else 'ECHOUE'}")

    # Matrice de confusion
    cm = confusion_matrix(y_test, y_pred)
    print("\n=== MATRICE DE CONFUSION ===")
    cm_df = pd.DataFrame(cm, index=class_names, columns=class_names)
    print(cm_df)

    return {
        "model": model,
        "label_encoder": le,
        "feature_names": feature_names,
        "report": report,
        "confusion_matrix": cm.tolist(),
        "class_names": list(class_names),
        "sensibilite_palu_grave": float(sensibilite_palu_grave),
        "sensibilite_tb": float(sensibilite_tb),
        "criteria_met": success_palu and success_tb
    }


def save_model(results: dict) -> None:
    """Sauvegarde le modèle entraîné et les métadonnées."""
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Sauvegarde modèle + encodeur
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump({
            "model": results["model"],
            "label_encoder": results["label_encoder"],
            "feature_names": results["feature_names"]
        }, f)

    # Sauvegarde des noms de features
    with open(FEATURE_NAMES_PATH, 'w', encoding='utf-8') as f:
        json.dump(results["feature_names"], f, ensure_ascii=False, indent=2)

    print(f"\nModèle sauvegardé : {MODEL_PATH}")
    print(f"Features sauvegardées : {FEATURE_NAMES_PATH}")


def load_model() -> dict:
    """Charge le modèle entraîné depuis le disque."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Modèle non trouvé : {MODEL_PATH}. Lancer train_model() d'abord.")

    with open(MODEL_PATH, 'rb') as f:
        data = pickle.load(f)

    return data


if __name__ == "__main__":
    print("=== Entraînement modèle HealthGuard IA ===")
    results = train_model()
    save_model(results)
    print("\nEntraînement terminé.")
