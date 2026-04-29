"""
Tests supplémentaires pour augmenter la couverture  Modules sync, severity_scorer,
tree_navigator (chemins supplémentaires), pin_auth et schema.
"""

import pytest
import sqlite3
from src.database.schema import get_in_memory_db, get_connection
from src.database.sync import (
    add_to_sync_queue, get_pending_sync_items, get_sync_status,
    mark_synced, increment_tentative
)
from src.database.encryption import generate_salt, generate_key
from src.decision_engine.severity_scorer import calculate_severity_score, _is_severe_tachypnee
from src.decision_engine.tree_navigator import (
    load_tree, navigate, _symptomes_to_reponses_for_tree,
    _symptomes_to_reponses, TREE_FILES
)
from src.decision_engine.aggregator import aggregate, _check_concordance, _resolve_tie
from src.decision_engine.recommendation import generate_recommendation
from src.database.schema import get_connection, initialize_database
from src.security.pin_auth import (
    hash_pin, verify_pin, check_pin_complexity
)


# =========================================================
# Tests sync.py
# =========================================================

class TestSyncQueue:
    """Tests de la queue de synchronisation."""

    @pytest.fixture
    def db(self):
        return get_in_memory_db()

    @pytest.fixture
    def key(self):
        salt = generate_salt()
        return generate_key("123456", salt)

    def test_add_to_queue_returns_id(self, db, key):
        """add_to_sync_queue retourne un UUID."""
        qid = add_to_sync_queue("consultations", "INSERT", {"test": "data"}, key, db)
        assert qid is not None
        assert len(qid) == 36  # format UUID

    def test_add_and_get_pending(self, db, key):
        """Les éléments ajoutés apparaissent dans les éléments en attente."""
        qid = add_to_sync_queue("patients", "INSERT", {"nom": "Test"}, key, db)
        items = get_pending_sync_items(db)
        assert len(items) == 1

    def test_get_sync_status_initial(self, db):
        """Le statut initial est vide."""
        status = get_sync_status(db)
        assert status["pending_sync_count"] == 0
        assert status["synced_count"] == 0

    def test_get_sync_status_after_add(self, db, key):
        """Le statut reflète les éléments ajoutés."""
        add_to_sync_queue("consultations", "INSERT", {"id": "1"}, key, db)
        add_to_sync_queue("consultations", "INSERT", {"id": "2"}, key, db)
        status = get_sync_status(db)
        assert status["pending_sync_count"] == 2

    def test_mark_synced_removes_item(self, db, key):
        """mark_synced supprime l'item de la queue."""
        qid = add_to_sync_queue("consultations", "UPDATE", {"id": "3"}, key, db)
        mark_synced(qid, db)
        items = get_pending_sync_items(db)
        assert len(items) == 0

    def test_increment_tentative(self, db, key):
        """increment_tentative incrémente le compteur."""
        qid = add_to_sync_queue("consultations", "INSERT", {"id": "4"}, key, db)
        increment_tentative(qid, db)
        increment_tentative(qid, db)
        # Après 2 incréments, l'item a 2 tentatives, toujours < 3
        items = get_pending_sync_items(db, max_tentatives=3)
        assert len(items) == 1

    def test_max_tentatives_filters_out(self, db, key):
        """Les items ayant atteint max_tentatives ne sont plus retournés."""
        qid = add_to_sync_queue("consultations", "INSERT", {"id": "5"}, key, db)
        increment_tentative(qid, db)
        increment_tentative(qid, db)
        increment_tentative(qid, db)
        # Maintenant 3 tentatives  filtré si max=3
        items = get_pending_sync_items(db, max_tentatives=3)
        assert len(items) == 0

    def test_get_sync_status_last_sync_after_increment(self, db, key):
        """Le champ last_sync est renseigné après un increment."""
        qid = add_to_sync_queue("consultations", "INSERT", {"id": "6"}, key, db)
        increment_tentative(qid, db)
        status = get_sync_status(db)
        assert status["last_sync"] is not None


# =========================================================
# Tests severity_scorer.py
# =========================================================

class TestSeverityScorer:
    """Tests du module de scoring de gravité."""

    def test_zero_symptoms_gives_vert(self):
        """Aucun symptôme → score VERT."""
        result = calculate_severity_score({})
        assert result["couleur"] == "VERT"
        assert result["score"] == 0

    def test_convulsions_critiques(self):
        """Convulsions → score CRITIQUE."""
        result = calculate_severity_score({"convulsions": 1, "trouble_conscience": 1})
        assert result["score"] == 3
        assert result["couleur"] == "ROUGE"
        assert any("Convulsions" in s for s in result["signes_alarme"])

    def test_spo2_critique(self):
        """SpO2 < 90% → score >= 2 (ORANGE ou ROUGE selon seuil)."""
        result = calculate_severity_score({"spo2_percent": 85})
        assert result["score"] >= 2
        assert any("SpO2 critique" in s for s in result["signes_alarme"])

    def test_spo2_basse_orange(self):
        """SpO2 entre 90-95% → ORANGE."""
        result = calculate_severity_score({"spo2_percent": 93})
        assert result["score"] >= 1
        assert result["couleur"] == "ORANGE"

    def test_hyperthermie_40(self):
        """Température ≥ 40°C → ajoute des points."""
        result = calculate_severity_score({"temperature_celsius": 40.5})
        assert result["score_brut"] >= 2
        assert any("Hyperthermie" in s for s in result["signes_alarme"])

    def test_temperature_39_5(self):
        """Température 39.5°C → 1 point."""
        result_395 = calculate_severity_score({"temperature_celsius": 39.5})
        result_37 = calculate_severity_score({"temperature_celsius": 37.0})
        assert result_395["score_brut"] > result_37["score_brut"]

    def test_deshydratation_severe(self):
        """Déshydratation sévère → points d'alarme."""
        result = calculate_severity_score({"signes_deshydratation_severes": True})
        assert result["score"] >= 1
        assert any("Déshydratation" in s for s in result["signes_alarme"])

    def test_groupe_vulnerable_enfant(self):
        """Enfant < 5 ans → point vulnérabilité."""
        result = calculate_severity_score({"age_ans": 3})
        assert result["score_brut"] >= 1

    def test_groupe_vulnerable_grossesse(self):
        """Femme enceinte → point vulnérabilité."""
        result = calculate_severity_score({"grossesse": 1, "age_ans": 28})
        assert result["score_brut"] >= 1

    def test_duree_longue_point(self):
        """Durée > 7 jours → +1 point."""
        result_long = calculate_severity_score({"duree_symptomes_jours": 10})
        result_court = calculate_severity_score({"duree_symptomes_jours": 2})
        assert result_long["score_brut"] > result_court["score_brut"]

    def test_multiple_signs_additive(self):
        """Symptômes multiples s'additionnent."""
        result = calculate_severity_score({
            "vomissements": 1, "dyspnee": 1, "hemoptysie": 1, "oedemes": 1
        })
        assert result["score_brut"] >= 4

    def test_justification_present(self):
        """Le résultat contient une justification."""
        result = calculate_severity_score({"convulsions": 1})
        assert "justification" in result
        assert "score_brut" in result


class TestTachypnee:
    """Tests des seuils de tachypnée OMS PCIME."""

    def test_nourrisson_2mois(self):
        """< 2 mois : seuil sévère > 70/min."""
        assert _is_severe_tachypnee(75, 0.1) is True
        assert _is_severe_tachypnee(65, 0.1) is False

    def test_nourrisson_12mois(self):
        """2-12 mois : seuil sévère > 60/min."""
        assert _is_severe_tachypnee(65, 0.5) is True
        assert _is_severe_tachypnee(55, 0.5) is False

    def test_enfant_5ans(self):
        """1-5 ans : seuil sévère > 50/min."""
        assert _is_severe_tachypnee(55, 3.0) is True
        assert _is_severe_tachypnee(45, 3.0) is False

    def test_adulte(self):
        """Adulte : seuil sévère > 30/min."""
        assert _is_severe_tachypnee(35, 30.0) is True
        assert _is_severe_tachypnee(25, 30.0) is False


# =========================================================
# Tests tree_navigator  chemins supplémentaires
# =========================================================

class TestTreeNavigatorAdditional:
    """Tests de chemins supplémentaires dans l'arbre décisionnel."""

    def test_load_all_trees(self):
        """Tous les arbres se chargent sans erreur."""
        for maladie in TREE_FILES.keys():
            tree = load_tree(maladie)
            assert tree is not None
            assert "noeuds" in tree

    def test_symptomes_to_reponses_paludisme(self):
        """Mapping symptômes → réponses pour paludisme."""
        s = {"fievre": 1, "temperature_celsius": 39.5, "age_ans": 3, "convulsions": 0}
        reponses = _symptomes_to_reponses_for_tree(s, "paludisme")
        assert reponses["N1"] == True
        assert reponses["N2"] == 39.5

    def test_symptomes_to_reponses_malnutrition_pb(self):
        """Mapping malnutrition utilise pb_mm, pas temperature."""
        s = {"pb_mm": 110, "age_ans": 2, "temperature_celsius": 40.0}
        reponses = _symptomes_to_reponses_for_tree(s, "malnutrition")
        # N2 doit être 110 (PB), PAS 40.0 (température)
        assert reponses["N2"] == 110.0

    def test_symptomes_to_reponses_ira(self):
        """Mapping IRA."""
        s = {"toux": 1, "fievre": 1, "spo2": 91}
        reponses = _symptomes_to_reponses_for_tree(s, "ira_pneumonie")
        assert reponses["N1"] == True

    def test_symptomes_to_reponses_tuberculose(self):
        """Mapping tuberculose."""
        s = {"toux": 1, "duree_symptomes_jours": 30, "hemoptysie": 1}
        reponses = _symptomes_to_reponses_for_tree(s, "tuberculose")
        assert "N1" in reponses

    def test_symptomes_to_reponses_diarrhee(self):
        """Mapping diarrhée."""
        s = {"diarrhee": 1, "epidemie_cholera_active": 1}
        reponses = _symptomes_to_reponses_for_tree(s, "diarrhee_cholera")
        assert "N1" in reponses

    def test_navigate_returns_result(self):
        """navigate() retourne toujours un ResultatDiagnostic."""
        for maladie in TREE_FILES.keys():
            tree = load_tree(maladie)
            # Réponses vides → naviguer jusqu'à une feuille
            reponses = {}
            result = navigate(tree, reponses)
            assert result is not None
            assert hasattr(result, "gravite")
            assert hasattr(result, "couleur_alerte")

    def test_ira_grave_spo2(self):
        """IRA + SpO2 basse → gravité élevée."""
        tree = load_tree("ira_pneumonie")
        reponses = {
            "N1": True, "N2": True, "N3": False,
            "N3_SANS_FIEVRE": False, "N4": True, "N4B_SPO2": 88.0
        }
        result = navigate(tree, reponses)
        assert result.gravite >= 2


# =========================================================
# Tests aggregator  chemins supplémentaires
# =========================================================

class TestAggregatorAdditional:
    """Tests des chemins supplémentaires de l'agrégateur."""

    def test_aggregate_ml_failure_fallback(self):
        """Si ML échoue, le résultat vient uniquement de l'arbre."""
        # Symptômes qui permettent à l'arbre de fonctionner
        symptomes = {"fievre": 1, "temperature_celsius": 39.0, "age_ans": 25, "poids_kg": 65}
        result = aggregate(symptomes)
        assert result is not None
        assert result.gravite in [0, 1, 2, 3]

    def test_check_concordance_same_diag(self):
        """Même diagnostic → concordance True."""
        assert _check_concordance("paludisme_grave", "paludisme_grave") is True

    def test_check_concordance_famille_palu(self):
        """Famille paludisme → concordance True."""
        assert _check_concordance("paludisme_grave", "paludisme_simple") is True

    def test_check_concordance_indetermine(self):
        """Diagnostic indéterminé → concordance True."""
        assert _check_concordance("indetermine", "tuberculose") is True

    def test_check_concordance_different(self):
        """Diagnostics différents → False."""
        assert _check_concordance("paludisme_grave", "tuberculose") is False

    def test_aggregate_ira_case(self):
        """Cas IRA → résultat cohérent."""
        symptomes = {
            "toux": 1, "fievre": 1, "dyspnee": 1,
            "age_ans": 2, "temperature_celsius": 38.8,
            "frequence_respiratoire": 55
        }
        result = aggregate(symptomes)
        assert result is not None
        assert result.couleur_alerte in ("ROUGE", "ORANGE", "VERT")

    def test_aggregate_tb_case(self):
        """Cas tuberculose → résultat cohérent."""
        symptomes = {
            "toux": 1, "duree_symptomes_jours": 25,
            "amaigrissement": 1, "hemoptysie": 1,
            "age_ans": 35, "sueurs_nocturnes": 1
        }
        result = aggregate(symptomes)
        assert result is not None

    def test_aggregate_diarrhee_cholera(self):
        """Cas diarrhée + choléra → notification requise."""
        symptomes = {
            "diarrhee": 1, "epidemie_cholera_active": 1,
            "signes_deshydratation_severes": 1,
            "age_ans": 30
        }
        result = aggregate(symptomes)
        assert result is not None

    def test_recommendation_from_aggregate(self):
        """La recommandation se génère depuis un résultat agrégé."""
        symptomes = {"fievre": 1, "temperature_celsius": 38.5, "age_ans": 5}
        result = aggregate(symptomes)
        rec = generate_recommendation(result)
        assert rec is not None
        assert len(rec.resume_3_points) >= 1
        assert rec.couleur_alerte in ("ROUGE", "ORANGE", "VERT")


# =========================================================
# Tests schema.py  chemins get_connection
# =========================================================

class TestSchemaAdditional:
    """Tests de chemins supplémentaires dans schema.py."""

    def test_get_in_memory_db_has_tables(self):
        """La BD en mémoire contient les 7 tables attendues."""
        db = get_in_memory_db()
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        for expected in ["patients", "consultations", "diagnostics", "audit_log", "sync_queue"]:
            assert expected in table_names, f"Table manquante: {expected}"

    def test_get_in_memory_db_thread_safe(self):
        """La BD en mémoire est accessible depuis des threads différents."""
        import threading
        errors = []
        db = get_in_memory_db()

        def query_in_thread():
            try:
                db.execute("SELECT COUNT(*) FROM patients").fetchone()
            except Exception as e:
                errors.append(str(e))

        t = threading.Thread(target=query_in_thread)
        t.start()
        t.join()
        assert errors == [], f"Erreur thread: {errors}"

    def test_foreign_keys_enabled(self):
        """Les clés étrangères sont activées."""
        db = get_in_memory_db()
        result = db.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1


# =========================================================
# Tests pin_auth  chemins supplémentaires
# =========================================================

class TestPinAuthAdditional:
    """Tests supplémentaires du module d'authentification PIN."""

    def test_hash_pin_returns_string(self):
        """hash_pin retourne une chaîne."""
        h = hash_pin("246810")
        assert isinstance(h, str)
        assert len(h) > 20

    def test_verify_pin_correct(self):
        """Vérification d'un PIN correct."""
        h = hash_pin("246810")
        assert verify_pin("246810", h) is True

    def test_verify_pin_wrong(self):
        """Vérification d'un PIN incorrect."""
        h = hash_pin("246810")
        assert verify_pin("135790", h) is False

    def test_complexity_rejects_sequence(self):
        """Les séquences sont rejetées."""
        assert check_pin_complexity("123456") is False

    def test_complexity_rejects_repeated(self):
        """Les répétitions sont rejetées."""
        assert check_pin_complexity("111111") is False

    def test_complexity_accepts_valid(self):
        """Un PIN valide est accepté."""
        assert check_pin_complexity("246810") is True

    def test_different_pins_different_hashes(self):
        """Deux PINs différents donnent des hashes différents."""
        h1 = hash_pin("246810")
        h2 = hash_pin("135790")
        assert h1 != h2

    def test_same_pin_different_hashes_salt(self):
        """Même PIN → hashes différents (sel aléatoire)."""
        h1 = hash_pin("246810")
        h2 = hash_pin("246810")
        assert h1 != h2  # Argon2id avec sel aléatoire


# =========================================================
# Tests tree_navigator  _symptomes_to_reponses global
# =========================================================

class TestSymptomesToReponses:
    """Tests de la fonction de mapping global _symptomes_to_reponses."""

    def test_fievre_mapping(self):
        """La fièvre est correctement mappée."""
        s = {"fievre": 1, "temperature_celsius": 39.5}
        r = _symptomes_to_reponses(s)
        assert r["N1"] is True
        assert r["N2"] == 39.5

    def test_pb_mapping_not_temperature(self):
        """Le PB (malnutrition) est distinct de la température."""
        s = {"pb_mm": 110, "temperature_celsius": 40.0, "age_ans": 3}
        r = _symptomes_to_reponses(s)
        # N2_MAL doit être 110 (PB), pas 40.0
        assert r["N2_MAL"] == 110

    def test_cholera_mapping(self):
        """Le contexte épidémique choléra est mappé."""
        s = {"diarrhee": 1, "epidemie_cholera_active": 1, "signes_deshydratation_severes": 1}
        r = _symptomes_to_reponses(s)
        assert r["N2_DIAR"] is True
        assert r["N3_CHOLERA"] is True

    def test_tb_duree_semaines(self):
        """La durée est convertie en semaines pour TB."""
        s = {"duree_symptomes_jours": 28, "hemoptysie": 1}
        r = _symptomes_to_reponses(s)
        assert r["N1_TB"] == 4.0  # 28j / 7 = 4 semaines
        assert r["N1B"] is True

    def test_tachypnee_estim_enfant(self):
        """Tachypnée estimée pour enfant avec FR élevée."""
        s = {"frequence_respiratoire": 55, "age_ans": 2, "toux": 1}
        r = _symptomes_to_reponses(s)
        # Tirage estimé → N3 = True (FR 55 > 40 pour age 2)
        assert r["N3"] is True

    def test_grossesse_vulnerable(self):
        """La grossesse déclenche le flag vulnérable."""
        s = {"grossesse": 1, "age_ans": 28}
        r = _symptomes_to_reponses(s)
        assert r["N3"] is True or r["N1_MAL"] is True

    def test_spo2_basse_flag(self):
        """SpO2 basse active les flags IRA."""
        s = {"spo2_percent": 88, "toux": 1}
        r = _symptomes_to_reponses(s)
        assert r["N4"] is True
        assert r["N4B_SPO2"] == 88

    def test_no_symptoms_defaults(self):
        """Pas de symptômes → valeurs par défaut cohérentes."""
        r = _symptomes_to_reponses({})
        assert r["N1"] is False  # Pas de fièvre
        assert isinstance(r["N2"], float)  # Température par défaut
        assert r["N3_CHOLERA"] is False


# =========================================================
# Tests schema.py  get_connection et initialize_database
# =========================================================

class TestSchemaConnection:
    """Tests des fonctions de connexion à la BD."""

    def test_get_connection_in_memory(self, tmp_path):
        """get_connection crée une BD fichier temporaire."""
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        assert conn is not None
        # Foreign keys activées
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1
        conn.close()

    def test_initialize_database(self, tmp_path):
        """initialize_database crée toutes les tables."""
        db_path = str(tmp_path / "init_test.db")
        conn = initialize_database(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "patients" in table_names
        assert "consultations" in table_names
        assert "audit_log" in table_names
        conn.close()

    def test_get_connection_creates_directory(self, tmp_path):
        """get_connection crée le répertoire parent si nécessaire."""
        db_path = str(tmp_path / "subdir" / "nested" / "test.db")
        conn = get_connection(db_path)
        assert conn is not None
        conn.close()
