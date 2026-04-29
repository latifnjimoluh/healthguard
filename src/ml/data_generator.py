"""
Générateur de dataset synthétique pour l'entraînement du modèle HealthGuard IA.
Génère 5000 cas cliniques réalistes basés sur l'épidémiologie des régions Adamaoua et Est-Cameroun.
"""

import numpy as np
import pandas as pd
from pathlib import Path

# Chemin de sortie
OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "ml" / "dataset_synthetique.csv"

# Distributions par classe (prévalences cibles)
PREVALENCES = {
    "paludisme_simple":  0.35,
    "paludisme_grave":   0.15,
    "ira_pneumonie":     0.20,
    "malnutrition_mas":  0.08,
    "diarrhee_cholera":  0.12,
    "tuberculose":       0.10
}

CLASSES = list(PREVALENCES.keys())
TOTAL_CASES = 5000


def generate_dataset(n_cases: int = TOTAL_CASES, seed: int = 42) -> pd.DataFrame:
    """
    Génère un dataset synthétique de n_cases cas cliniques.

    Les distributions des features sont basées sur les caractéristiques
    épidémiologiques réelles des régions Adamaoua et Est-Cameroun.

    Args:
        n_cases: Nombre de cas à générer
        seed: Graine aléatoire pour reproductibilité

    Returns:
        DataFrame pandas avec les 24 features + label
    """
    np.random.seed(seed)
    records = []

    # Nombre de cas par classe
    counts = {cls: int(n_cases * prev) for cls, prev in PREVALENCES.items()}
    # Ajustement pour atteindre exactement n_cases
    total = sum(counts.values())
    counts["paludisme_simple"] += n_cases - total

    for label, count in counts.items():
        for _ in range(count):
            record = _generate_case(label)
            record["label"] = label
            records.append(record)

    df = pd.DataFrame(records)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def _generate_case(label: str) -> dict:
    """
    Génère un cas clinique synthétique pour une maladie donnée.

    Les paramètres (moyenne, écart-type, probabilités) sont basés sur
    les données cliniques réelles des maladies cibles.
    """
    case = {}

    if label == "paludisme_simple":
        case.update(_gen_paludisme_simple())
    elif label == "paludisme_grave":
        case.update(_gen_paludisme_grave())
    elif label == "ira_pneumonie":
        case.update(_gen_ira_pneumonie())
    elif label == "malnutrition_mas":
        case.update(_gen_malnutrition())
    elif label == "diarrhee_cholera":
        case.update(_gen_diarrhee_cholera())
    elif label == "tuberculose":
        case.update(_gen_tuberculose())

    return case


def _base_case() -> dict:
    """Génère les valeurs de base communes à tous les cas."""
    age = max(0.1, np.random.exponential(15))
    age = min(age, 99)
    sexe = np.random.binomial(1, 0.5)
    grossesse = np.random.binomial(1, 0.15) if sexe == 0 and 15 <= age <= 45 else 0
    poids = max(3.0, np.random.normal(50, 20))
    saison_pluie = np.random.binomial(1, 0.55)  # 55% du temps = saison pluies
    zone_endemie_tb = np.random.binomial(1, 0.4)
    contact_tb_connu = np.random.binomial(1, 0.08)
    epidemie_cholera_active = np.random.binomial(1, 0.05)

    return {
        "age_ans": round(age, 1),
        "poids_kg": round(poids, 1),
        "sexe": sexe,
        "grossesse": grossesse,
        "saison_pluie": saison_pluie,
        "zone_endemie_tb": zone_endemie_tb,
        "contact_tb_connu": contact_tb_connu,
        "epidemie_cholera_active": epidemie_cholera_active
    }


def _gen_paludisme_simple() -> dict:
    """Cas paludisme non compliqué  présentation typique."""
    base = _base_case()
    base.update({
        "fievre": 1,
        "toux": np.random.binomial(1, 0.20),
        "diarrhee": np.random.binomial(1, 0.15),
        "vomissements": np.random.binomial(1, 0.35),
        "cephalee": np.random.binomial(1, 0.85),
        "frissons": np.random.binomial(1, 0.80),
        "courbatures": np.random.binomial(1, 0.75),
        "dyspnee": 0,
        "hemoptysie": 0,
        "oedemes": 0,
        "convulsions": 0,
        "trouble_conscience": 0,
        "temperature_celsius": round(np.random.normal(38.9, 0.6), 1),
        "frequence_respiratoire": int(np.random.normal(22, 4)),
        "spo2_percent": round(np.random.normal(97, 1.5), 0),
        "duree_symptomes_jours": max(1, int(np.random.exponential(3)))
    })
    base["temperature_celsius"] = np.clip(base["temperature_celsius"], 38.0, 40.5)
    base["frequence_respiratoire"] = np.clip(base["frequence_respiratoire"], 16, 30)
    return base


def _gen_paludisme_grave() -> dict:
    """Cas paludisme grave  signes de gravité présents."""
    base = _base_case()
    # Paludisme grave touche surtout les enfants <5 ans et femmes enceintes
    if np.random.random() < 0.60:
        base["age_ans"] = round(max(0.2, np.random.exponential(3)), 1)
        base["poids_kg"] = round(max(4, np.random.normal(base["age_ans"] * 3 + 5, 2)), 1)

    base.update({
        "fievre": 1,
        "toux": np.random.binomial(1, 0.25),
        "diarrhee": np.random.binomial(1, 0.20),
        "vomissements": np.random.binomial(1, 0.80),
        "cephalee": np.random.binomial(1, 0.70),
        "frissons": np.random.binomial(1, 0.60),
        "courbatures": np.random.binomial(1, 0.65),
        "dyspnee": np.random.binomial(1, 0.30),
        "hemoptysie": 0,
        "oedemes": np.random.binomial(1, 0.10),
        "convulsions": np.random.binomial(1, 0.65),
        "trouble_conscience": np.random.binomial(1, 0.60),
        "temperature_celsius": round(np.random.normal(39.8, 0.8), 1),
        "frequence_respiratoire": int(np.random.normal(32, 8)),
        "spo2_percent": round(np.random.normal(93, 3), 0),
        "duree_symptomes_jours": max(1, int(np.random.normal(3, 1.5)))
    })
    base["temperature_celsius"] = np.clip(base["temperature_celsius"], 38.5, 42.0)
    base["frequence_respiratoire"] = np.clip(base["frequence_respiratoire"], 20, 60)
    base["spo2_percent"] = np.clip(base["spo2_percent"], 80, 97)
    return base


def _gen_ira_pneumonie() -> dict:
    """Cas IRA/Pneumonie  symptômes respiratoires dominants."""
    base = _base_case()
    age = base["age_ans"]

    # Calcul FR selon âge
    if age < 2/12:
        fr_base, fr_std = 65, 10
    elif age < 1:
        fr_base, fr_std = 52, 8
    elif age <= 5:
        fr_base, fr_std = 45, 8
    else:
        fr_base, fr_std = 32, 6

    base.update({
        "fievre": np.random.binomial(1, 0.85),
        "toux": 1,
        "diarrhee": np.random.binomial(1, 0.10),
        "vomissements": np.random.binomial(1, 0.20),
        "cephalee": np.random.binomial(1, 0.30),
        "frissons": np.random.binomial(1, 0.25),
        "courbatures": np.random.binomial(1, 0.20),
        "dyspnee": np.random.binomial(1, 0.75),
        "hemoptysie": np.random.binomial(1, 0.05),
        "oedemes": 0,
        "convulsions": np.random.binomial(1, 0.05),
        "trouble_conscience": np.random.binomial(1, 0.05),
        "temperature_celsius": round(np.random.normal(38.7, 0.7), 1),
        "frequence_respiratoire": int(np.random.normal(fr_base, fr_std)),
        "spo2_percent": round(np.random.normal(92, 4), 0),
        "duree_symptomes_jours": max(1, int(np.random.normal(4, 2)))
    })
    base["temperature_celsius"] = np.clip(base["temperature_celsius"], 37.0, 41.0)
    base["frequence_respiratoire"] = max(20, base["frequence_respiratoire"])
    base["spo2_percent"] = np.clip(base["spo2_percent"], 78, 99)
    return base


def _gen_malnutrition() -> dict:
    """Cas malnutrition aiguë sévère  enfant <5 ans majoritairement."""
    base = _base_case()
    # MAS touche surtout les enfants <5 ans
    age = round(max(0.2, np.random.exponential(2)), 1)
    age = min(age, 5)
    base["age_ans"] = age
    poids = max(2.0, age * 3 - np.random.normal(3, 1))
    base["poids_kg"] = round(max(2.0, poids), 1)

    base.update({
        "fievre": np.random.binomial(1, 0.35),
        "toux": np.random.binomial(1, 0.20),
        "diarrhee": np.random.binomial(1, 0.30),
        "vomissements": np.random.binomial(1, 0.20),
        "cephalee": 0,
        "frissons": np.random.binomial(1, 0.10),
        "courbatures": np.random.binomial(1, 0.10),
        "dyspnee": np.random.binomial(1, 0.10),
        "hemoptysie": 0,
        "oedemes": np.random.binomial(1, 0.40),  # Kwashiorkor fréquent
        "convulsions": np.random.binomial(1, 0.05),
        "trouble_conscience": np.random.binomial(1, 0.10),
        "temperature_celsius": round(np.random.normal(36.9, 0.5), 1),
        "frequence_respiratoire": int(np.random.normal(28, 6)),
        "spo2_percent": round(np.random.normal(96, 2), 0),
        "duree_symptomes_jours": max(7, int(np.random.normal(21, 10)))
    })
    base["temperature_celsius"] = np.clip(base["temperature_celsius"], 35.0, 39.5)
    base["frequence_respiratoire"] = np.clip(base["frequence_respiratoire"], 20, 50)
    return base


def _gen_diarrhee_cholera() -> dict:
    """Cas diarrhée aiguë/choléra suspect."""
    base = _base_case()
    is_cholera = np.random.random() < 0.30  # 30% des cas de diarrhée = suspect choléra

    base.update({
        "fievre": np.random.binomial(1, 0.55),
        "toux": np.random.binomial(1, 0.10),
        "diarrhee": 1,
        "vomissements": np.random.binomial(1, 0.65),
        "cephalee": np.random.binomial(1, 0.25),
        "frissons": np.random.binomial(1, 0.15),
        "courbatures": np.random.binomial(1, 0.20),
        "dyspnee": np.random.binomial(1, 0.10),
        "hemoptysie": 0,
        "oedemes": np.random.binomial(1, 0.05),
        "convulsions": np.random.binomial(1, 0.05),
        "trouble_conscience": np.random.binomial(1, 0.10),
        "temperature_celsius": round(np.random.normal(37.8, 0.8), 1),
        "frequence_respiratoire": int(np.random.normal(22, 5)),
        "spo2_percent": round(np.random.normal(96, 2), 0),
        "duree_symptomes_jours": max(1, int(np.random.exponential(2))),
        "epidemie_cholera_active": 1 if is_cholera else np.random.binomial(1, 0.05)
    })
    base["temperature_celsius"] = np.clip(base["temperature_celsius"], 36.5, 40.0)
    return base


def _gen_tuberculose() -> dict:
    """Cas tuberculose pulmonaire  adulte majoritairement, toux prolongée."""
    base = _base_case()
    # TB touche surtout les adultes 15-60 ans
    age = round(max(15, np.random.normal(38, 15)), 1)
    age = min(age, 75)
    base["age_ans"] = age
    base["poids_kg"] = round(max(35, np.random.normal(58, 12)), 1)
    # Zone endémie TB Est-Cameroun
    base["zone_endemie_tb"] = 1
    base["contact_tb_connu"] = np.random.binomial(1, 0.30)

    duree_jours = max(21, int(np.random.normal(42, 14)))

    base.update({
        "fievre": np.random.binomial(1, 0.45),  # Fièvre vespérale, pas systématique
        "toux": 1,
        "diarrhee": np.random.binomial(1, 0.05),
        "vomissements": np.random.binomial(1, 0.05),
        "cephalee": np.random.binomial(1, 0.15),
        "frissons": np.random.binomial(1, 0.20),
        "courbatures": np.random.binomial(1, 0.25),
        "dyspnee": np.random.binomial(1, 0.40),
        "hemoptysie": np.random.binomial(1, 0.50),
        "oedemes": np.random.binomial(1, 0.05),
        "convulsions": 0,
        "trouble_conscience": np.random.binomial(1, 0.03),
        "temperature_celsius": round(np.random.normal(36.8, 0.5), 1),  # Souvent afébrile
        "frequence_respiratoire": int(np.random.normal(22, 5)),
        "spo2_percent": round(np.random.normal(95, 3), 0),
        "duree_symptomes_jours": duree_jours
    })
    base["temperature_celsius"] = np.clip(base["temperature_celsius"], 35.5, 39.5)
    base["frequence_respiratoire"] = np.clip(base["frequence_respiratoire"], 14, 35)
    base["spo2_percent"] = np.clip(base["spo2_percent"], 82, 99)
    return base


def save_dataset(df: pd.DataFrame, path: Path = OUTPUT_PATH) -> None:
    """Sauvegarde le dataset en CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding='utf-8')
    print(f"Dataset sauvegardé : {path}")
    print(f"Dimensions : {df.shape}")
    print(f"\nDistribution des classes :")
    print(df["label"].value_counts(normalize=True).round(3))


def get_feature_names() -> list:
    """Retourne la liste ordonnée des 24 features d'entrée."""
    return [
        # Features binaires (12)
        "fievre", "toux", "diarrhee", "vomissements", "cephalee",
        "frissons", "courbatures", "dyspnee", "hemoptysie",
        "oedemes", "convulsions", "trouble_conscience",
        # Features numériques (6)
        "temperature_celsius", "age_ans", "poids_kg",
        "frequence_respiratoire", "spo2_percent", "duree_symptomes_jours",
        # Features contextuelles (4)
        "saison_pluie", "zone_endemie_tb", "contact_tb_connu", "epidemie_cholera_active",
        # Features démographiques (2)
        "sexe", "grossesse"
    ]


if __name__ == "__main__":
    print("Génération du dataset synthétique HealthGuard IA...")
    df = generate_dataset(TOTAL_CASES)
    save_dataset(df)
    print("\nAperçu des premières lignes :")
    print(df.head())
