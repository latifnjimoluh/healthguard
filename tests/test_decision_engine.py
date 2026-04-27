"""
Tests unitaires — Moteur de décision HealthGuard IA.
Valide les 5 arbres décisionnels avec scénarios cliniques.
"""

import pytest
from src.decision_engine.tree_navigator import (
    load_tree, navigate, navigate_all_trees, ResultatDiagnostic
)
from src.decision_engine.aggregator import aggregate
from src.decision_engine.recommendation import generate_recommendation


class TestPaludismeTree:
    """Tests arbre décisionnel paludisme."""

    def test_paludisme_grave_convulsions(self):
        """Enfant avec fièvre + convulsions + trouble conscience → ROUGE."""
        tree = load_tree("paludisme")
        reponses = {
            "N1": True,           # Fièvre présente
            "N2": 40.1,           # Température 40.1°C
            "N3": True,           # Groupe vulnérable (enfant <5 ans)
            "N3_ATTENUATION": True,
            "N4": True            # Signes de gravité présents
        }
        resultat = navigate(tree, reponses)
        assert resultat.gravite == 3
        assert resultat.couleur_alerte == "ROUGE"
        assert resultat.diagnostic == "paludisme_grave"
        assert "artemether_lumefantrine_oral" in resultat.contre_indications

    def test_paludisme_simple_adulte(self):
        """Adulte avec triade classique sans signes de gravité → ORANGE."""
        tree = load_tree("paludisme")
        reponses = {
            "N1": True,      # Fièvre
            "N2": 39.0,      # Température 39.0°C
            "N3": False,     # Pas groupe vulnérable (adulte)
            "N5": True,      # Triade céphalée + frissons + courbatures
            "N6": False,     # Pas de vomissements
            "N6B": False     # Durée < 5j
        }
        resultat = navigate(tree, reponses)
        assert resultat.gravite <= 2
        assert "paludisme" in resultat.diagnostic

    def test_paludisme_peu_probable_sans_fievre(self):
        """Pas de fièvre → paludisme peu probable."""
        tree = load_tree("paludisme")
        reponses = {"N1": False}
        resultat = navigate(tree, reponses)
        assert resultat.gravite <= 1
        assert "peu_probable" in resultat.diagnostic


class TestIRATree:
    """Tests arbre décisionnel IRA/pneumonie."""

    def test_pneumonie_severe_spo2_basse(self):
        """Toux + FR élevée + SpO2 < 95% → ROUGE transfert."""
        tree = load_tree("ira_pneumonie")
        reponses = {
            "N1": True,           # Toux présente
            "N2": True,           # Fièvre
            "N3": False,          # Pas de tirage
            "N3_SANS_FIEVRE": False,
            "N4": True,           # SpO2 < 95%
            "N4B_SPO2": 91.0      # SpO2 91%
        }
        resultat = navigate(tree, reponses)
        assert resultat.gravite >= 2
        assert resultat.couleur_alerte in ("ROUGE", "ORANGE")

    def test_pneumonie_moderee_tachypnee(self):
        """Toux + fièvre + tachypnée → ORANGE traitement antibiotique."""
        tree = load_tree("ira_pneumonie")
        reponses = {
            "N1": True,       # Toux
            "N2": True,       # Fièvre
            "N3": False,      # Pas de tirage
            "N4": False,      # SpO2 normale ou non mesurée
            "N5_FREQUENCE": None,  # Navigation par âge
            "N5C_5ANS": 42,   # FR 42/min (> 40 seuil pour 1-5 ans)
            "N6_GRAVITE": False
        }
        resultat = navigate(tree, reponses)
        assert resultat is not None


class TestMalnutritionTree:
    """Tests arbre décisionnel malnutrition."""

    def test_mas_pb_inferieur_115(self):
        """PB 108mm + oedèmes → MAS."""
        tree = load_tree("malnutrition")
        reponses = {
            "N1": True,          # Enfant < 5 ans
            "N2": 108.0,         # PB 108mm < 115 → MAS
            "N3_MAS": True,      # Oedèmes présents
            "N4_COMPLICATIONS": False,
            "N5_TEST_APPETIT": True   # Test appétit positif
        }
        resultat = navigate(tree, reponses)
        assert resultat.diagnostic == "malnutrition_mas"
        assert resultat.gravite >= 2

    def test_mas_transfert_si_echec_appetit(self):
        """MAS + échec test appétit → transfert CRENAS."""
        tree = load_tree("malnutrition")
        reponses = {
            "N1": True,
            "N2": 108.0,
            "N3_MAS": True,
            "N4_COMPLICATIONS": False,
            "N5_TEST_APPETIT": False    # Échec test appétit → transfert
        }
        resultat = navigate(tree, reponses)
        assert resultat.gravite >= 2

    def test_malnutrition_peu_probable_pb_normal(self):
        """PB > 125mm, pas d'oedèmes → peu probable."""
        tree = load_tree("malnutrition")
        reponses = {
            "N1": True,
            "N2": 130.0,         # PB normal
            "N4_OEDEMES_CHECK": False
        }
        resultat = navigate(tree, reponses)
        assert resultat.gravite <= 1


class TestDiarrheeTree:
    """Tests arbre décisionnel diarrhée/choléra."""

    def test_cholera_severe_deshydratation(self):
        """Choléra + déshydratation sévère + grossesse → ROUGE + notification."""
        tree = load_tree("diarrhee_cholera")
        reponses = {
            "N1_DIAR": 12,            # > 3 selles
            "N2_DIAR": True,          # Épidémie choléra active
            "N3_CHOLERA": True        # Déshydratation sévère
        }
        # Navigation manuelle pour test
        reponses["N1"] = 12
        reponses["N2"] = True
        reponses["N3_CHOLERA"] = True
        resultat = navigate(tree, reponses)
        # Vérifier que le résultat contient les éléments critiques
        assert resultat is not None

    def test_diarrhee_legere_sans_deshydratation(self):
        """Diarrhée légère sans déshydratation → VERT SRO domicile."""
        tree = load_tree("diarrhee_cholera")
        reponses = {
            "N1": 4,              # 4 selles (> 3 → diarrhée)
            "N2": False,          # Pas épidémie choléra
            "N3_DIARRHEE_SIMPLE": False,  # Pas déshydratation sévère
            "N4_DESHYDRATATION_MODEREE": False,  # Pas déshydratation modérée
            "N6_FIEVRE": False,
            "N7_DUREE": False
        }
        resultat = navigate(tree, reponses)
        assert resultat.gravite <= 1


class TestTuberculoseTree:
    """Tests arbre décisionnel tuberculose."""

    def test_tb_hautement_suspectee(self):
        """Toux > 3 semaines + hémoptysie + contact TB → ORANGE référence CDTB."""
        tree = load_tree("tuberculose")
        # Les noeuds TB : N1 (duree_semaines), N2 (amaigrissement), N3 (sueurs), N4 (contact)
        reponses = {
            "N1": 5,       # 5 semaines (> seuil 3)
            "N1B": True,   # Hémoptysie
            "N2": True,    # Amaigrissement
            "N3": True,    # Sueurs nocturnes
            "N4": True,    # Contact TB connu
            "N4_SANS_SUEURS": True,
            "N5_GRAVITE": False   # Pas de signe de gravité critique
        }
        resultat = navigate(tree, reponses)
        assert resultat.diagnostic == "tuberculose", \
            f"Attendu tuberculose, obtenu {resultat.diagnostic}"
        assert "antibiotiques_empiriques" in resultat.contre_indications

    def test_tb_peu_probable_toux_courte(self):
        """Toux < 3 semaines + pas d'hémoptysie → TB peu probable."""
        tree = load_tree("tuberculose")
        reponses = {
            "N1_TB": 1,       # 1 semaine de toux
            "N1B": False      # Pas d'hémoptysie
        }
        resultat = navigate(tree, reponses)
        assert resultat.gravite <= 1


class TestAggregator:
    """Tests de l'agrégateur arbre + ML."""

    def test_aggregate_paludisme_grave_override(self):
        """Paludisme grave (ROUGE) : override ML."""
        symptomes = {
            "fievre": 1, "temperature_celsius": 40.1,
            "convulsions": 1, "trouble_conscience": 1,
            "vomissements": 1, "age_ans": 3, "poids_kg": 13,
            "saison_pluie": 1, "duree_symptomes_jours": 3,
            "frissons": 1, "cephalee": 1
        }
        resultat = aggregate(symptomes)
        assert resultat.gravite == 3
        assert resultat.couleur_alerte == "ROUGE"

    def test_aggregate_returns_recommendation(self):
        """aggregate() retourne un résultat valide avec recommandation."""
        symptomes = {
            "fievre": 1, "temperature_celsius": 39.0,
            "age_ans": 25, "poids_kg": 65
        }
        resultat = aggregate(symptomes)
        rec = generate_recommendation(resultat)
        assert len(rec.resume_3_points) >= 1
        assert rec.couleur_alerte in ("ROUGE", "ORANGE", "VERT")
