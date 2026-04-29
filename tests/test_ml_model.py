"""
Tests unitaires  Modèle ML HealthGuard IA.
Couvre : inférence, performances (sensibilité), temps de réponse.
"""

import pytest
import time
from src.ml.inference import predict, ProbabilitesDiagnostic
from src.ml.data_generator import generate_dataset, get_feature_names


class TestMLInference:
    """Tests du module d'inférence ML."""

    def test_predict_returns_probabilities(self):
        """predict() retourne des probabilités pour les 6 classes."""
        symptomes = {
            "fievre": 1, "temperature_celsius": 39.5, "age_ans": 25,
            "poids_kg": 65, "frissons": 1, "cephalee": 1
        }
        result = predict(symptomes)
        assert isinstance(result, ProbabilitesDiagnostic)
        assert len(result.probabilites) == 6
        # Somme des probabilités ~ 1.0
        total = sum(result.probabilites.values())
        assert abs(total - 1.0) < 0.01

    def test_predict_paludisme_with_classic_symptoms(self):
        """Symptômes classiques de paludisme → diagnostic paludisme."""
        symptomes = {
            "fievre": 1, "temperature_celsius": 39.5,
            "frissons": 1, "cephalee": 1, "courbatures": 1,
            "vomissements": 1, "age_ans": 30, "saison_pluie": 1,
            "poids_kg": 65, "duree_symptomes_jours": 3
        }
        result = predict(symptomes)
        assert "paludisme" in result.top_1_diagnostic

    def test_predict_paludisme_grave_with_convulsions(self):
        """Paludisme avec convulsions → paludisme_grave."""
        symptomes = {
            "fievre": 1, "temperature_celsius": 40.1,
            "convulsions": 1, "trouble_conscience": 1,
            "vomissements": 1, "age_ans": 3, "poids_kg": 13,
            "saison_pluie": 1, "duree_symptomes_jours": 3
        }
        result = predict(symptomes)
        assert result.top_1_diagnostic == "paludisme_grave"
        assert result.top_1_probabilite > 0.70

    def test_predict_tuberculose_with_chronic_cough(self):
        """Toux chronique + hémoptysie → tuberculose."""
        symptomes = {
            "toux": 1, "hemoptysie": 1, "duree_symptomes_jours": 35,
            "age_ans": 42, "poids_kg": 58, "zone_endemie_tb": 1,
            "fievre": 0, "temperature_celsius": 37.1
        }
        result = predict(symptomes)
        assert result.top_1_diagnostic == "tuberculose"

    def test_predict_handles_missing_spo2(self):
        """predict() gère correctement l'absence de SpO2."""
        symptomes = {
            "toux": 1, "fievre": 1, "dyspnee": 1, "age_ans": 7,
            "frequence_respiratoire": 48, "poids_kg": 22
            # spo2_percent absent intentionnellement
        }
        result = predict(symptomes)
        assert result is not None
        assert "spo2_percent" in result.features_manquantes

    def test_predict_inference_time(self):
        """Temps d'inférence médian < 300ms."""
        symptomes = {
            "fievre": 1, "temperature_celsius": 39.0,
            "age_ans": 25, "poids_kg": 65
        }
        # Chauffe (premier appel charge le modèle)
        predict(symptomes)

        # Mesure sur 20 inférences
        times = []
        for _ in range(20):
            start = time.time()
            predict(symptomes)
            elapsed_ms = (time.time() - start) * 1000
            times.append(elapsed_ms)

        median_time = sorted(times)[len(times)//2]
        assert median_time < 300, f"Inférence trop lente : {median_time:.1f}ms (limite 300ms)"

    def test_predict_all_zeros(self):
        """predict() gère les symptômes tous à zéro."""
        symptomes = {f: 0 for f in get_feature_names()}
        symptomes["age_ans"] = 25
        symptomes["poids_kg"] = 60
        symptomes["temperature_celsius"] = 37.0
        result = predict(symptomes)
        assert result is not None


class TestMLPerformance:
    """Tests de performance du modèle ML sur dataset de test."""

    @pytest.fixture(scope="class")
    def test_dataset(self):
        """Dataset de test partagé entre les méthodes de la classe."""
        return generate_dataset(1000, seed=999)

    def test_paludisme_grave_sensitivity(self, test_dataset):
        """Sensibilité paludisme grave >= 85%."""
        df_pg = test_dataset[test_dataset["label"] == "paludisme_grave"]
        if len(df_pg) == 0:
            pytest.skip("Pas de cas paludisme_grave dans le dataset de test")

        from src.ml.data_generator import get_feature_names
        feature_names = get_feature_names()

        correct = 0
        for _, row in df_pg.iterrows():
            symptomes = {f: row[f] for f in feature_names if f in row.index}
            result = predict(symptomes)
            if result.top_1_diagnostic == "paludisme_grave":
                correct += 1

        sensitivity = correct / len(df_pg)
        assert sensitivity >= 0.85, f"Sensibilite paludisme_grave = {sensitivity:.1%} < 85%"

    def test_tuberculose_sensitivity(self, test_dataset):
        """Sensibilité tuberculose >= 80%."""
        df_tb = test_dataset[test_dataset["label"] == "tuberculose"]
        if len(df_tb) == 0:
            pytest.skip("Pas de cas tuberculose dans le dataset de test")

        from src.ml.data_generator import get_feature_names
        feature_names = get_feature_names()

        correct = 0
        for _, row in df_tb.iterrows():
            symptomes = {f: row[f] for f in feature_names if f in row.index}
            result = predict(symptomes)
            if result.top_1_diagnostic == "tuberculose":
                correct += 1

        sensitivity = correct / len(df_tb)
        assert sensitivity >= 0.80, f"Sensibilite tuberculose = {sensitivity:.1%} < 80%"
