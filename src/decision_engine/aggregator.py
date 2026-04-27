"""
Agrégateur du moteur de décision HealthGuard IA.
Combine les résultats de l'arbre décisionnel (60%) et du modèle ML (40%)
pour produire un diagnostic final pondéré.
"""

from dataclasses import dataclass
from typing import Optional
from src.decision_engine.tree_navigator import ResultatDiagnostic, load_tree, navigate, TREE_FILES
from src.ml.inference import predict, ProbabilitesDiagnostic


@dataclass
class ResultatFinal:
    """Résultat final agrégé du moteur de décision HealthGuard IA."""
    diagnostic_principal: str
    probabilite_combinee: float       # Probabilité pondérée (0.0 à 1.0)
    gravite: int                      # 0=faible, 1=modéré, 2=élevé, 3=critique
    couleur_alerte: str               # VERT, ORANGE, ROUGE
    action_immediate: str
    recommandation_courte: str
    recommandation_complete: str
    traitement: list
    contre_indications: list
    structure_reference: Optional[str]
    notification_district: bool
    # Diagnostics différentiels
    diagnostic_differentiel: Optional[str] = None
    proba_differentiel: float = 0.0
    # Métadonnées
    source_decision: str = "arbre+ml"  # 'arbre', 'ml', 'arbre+ml'
    resultat_arbre: Optional[ResultatDiagnostic] = None
    resultat_ml: Optional[ProbabilitesDiagnostic] = None
    suivi: Optional[str] = None


def aggregate(symptomes: dict) -> ResultatFinal:
    """
    Agrège les résultats de l'arbre décisionnel et du modèle ML.

    Règles de pondération :
    1. Si arbre retourne ROUGE (gravité=3) → override total, ignorer ML
    2. Si arbre a confiance > 90% (gravité claire) → poids arbre = 80%
    3. Sinon → pondération standard arbre 60% / ML 40%

    Args:
        symptomes: Dictionnaire des symptômes et valeurs mesurées

    Returns:
        ResultatFinal avec diagnostic agrégé et recommandations
    """
    # --- Étape 1 : Résultat de l'arbre décisionnel ---
    best_arbre = _get_best_tree_result(symptomes)

    # --- Étape 2 : Résultat du modèle ML ---
    try:
        resultat_ml = predict(symptomes)
    except Exception as e:
        # Si ML échoue, utiliser uniquement l'arbre
        return _arbre_only(best_arbre, f"ML indisponible : {e}")

    # --- Étape 3 : Application des règles de pondération ---

    # Règle 1 : Override si gravité critique (ROUGE)
    if best_arbre.gravite == 3 and best_arbre.couleur_alerte == "ROUGE":
        return _build_result(
            best_arbre, resultat_ml,
            source="arbre",
            override_message="Override ROUGE : arbre décisionnel prioritaire"
        )

    # Règle 2 : Concordance forte entre arbre et ML
    diag_arbre = best_arbre.diagnostic
    diag_ml = resultat_ml.top_1_diagnostic
    proba_ml = resultat_ml.top_1_probabilite

    concordance = _check_concordance(diag_arbre, diag_ml)

    if concordance and best_arbre.gravite >= 2:
        # Forte concordance + gravité élevée → poids arbre 80%
        proba_combinee = 0.80 * (best_arbre.gravite / 3) + 0.20 * proba_ml
        source = "arbre+ml_fort"
    elif concordance:
        # Concordance normale → pondération 60/40
        proba_combinee = 0.60 * (best_arbre.gravite / 3 + 0.5) / 1.5 + 0.40 * proba_ml
        source = "arbre+ml"
    else:
        # Discordance → l'arbre reste prioritaire mais ML donne le différentiel
        proba_combinee = 0.60 * (best_arbre.gravite / 3 + 0.3) + 0.40 * proba_ml * 0.5
        source = "arbre_discordant"

    return _build_result(
        best_arbre, resultat_ml,
        source=source,
        proba_override=proba_combinee
    )


def _get_best_tree_result(symptomes: dict) -> ResultatDiagnostic:
    """
    Exécute tous les arbres et retourne le résultat le plus grave.
    Chaque arbre reçoit son propre mapping de réponses.

    Args:
        symptomes: Dictionnaire de symptômes

    Returns:
        ResultatDiagnostic avec la plus haute gravité
    """
    from src.decision_engine.tree_navigator import _symptomes_to_reponses_for_tree

    best_result = None
    all_results = {}

    for maladie in TREE_FILES.keys():
        try:
            tree = load_tree(maladie)
            reponses = _symptomes_to_reponses_for_tree(symptomes, maladie)
            resultat = navigate(tree, reponses)
            resultat.maladie_testee = maladie
            all_results[maladie] = resultat

            if best_result is None or resultat.gravite > best_result.gravite:
                best_result = resultat
        except Exception:
            continue

    # Tiebreaking intelligent : si plusieurs arbres ont la même gravité max,
    # choisir celui dont le symptôme principal correspond aux données du patient
    if best_result is not None:
        max_gravite = best_result.gravite
        ties = [r for r in all_results.values() if r.gravite == max_gravite]
        if len(ties) > 1:
            best_result = _resolve_tie(ties, symptomes, all_results)

    if best_result is None:
        # Résultat par défaut si tous les arbres échouent
        best_result = ResultatDiagnostic(
            diagnostic="indetermine",
            gravite=1,
            couleur_alerte="ORANGE",
            action_immediate="EVALUATION_CLINIQUE",
            recommandation_courte="Évaluation clinique complète nécessaire",
            recommandation_complete="Le système n'a pu atteindre un diagnostic. Procéder à une évaluation clinique."
        )

    return best_result


def _resolve_tie(candidates: list, symptomes: dict, all_results: dict) -> 'ResultatDiagnostic':
    """
    Résout les égalités de gravité entre arbres en utilisant les symptômes dominants.

    Priorité :
    - Diarrhée + épidémie choléra → diarrhee_cholera
    - Toux + hémoptysie + durée longue → tuberculose
    - Toux + dyspnée + FR élevée → ira_pneumonie
    - Fièvre + convulsions → paludisme_grave
    - PB bas + oedèmes → malnutrition
    """
    # Diarrhée/choléra suspect → priorité si présent
    if symptomes.get("diarrhee") and (symptomes.get("epidemie_cholera_active") or
                                       symptomes.get("signes_deshydratation_severes")):
        if "diarrhee_cholera" in all_results:
            return all_results["diarrhee_cholera"]

    # Tuberculose : toux très longue + hémoptysie
    duree = symptomes.get("duree_symptomes_jours", 0) or 0
    if symptomes.get("hemoptysie") and duree > 20:
        if "tuberculose" in all_results:
            return all_results["tuberculose"]

    # IRA : toux + dyspnée + FR élevée
    if symptomes.get("toux") and symptomes.get("dyspnee"):
        if "ira_pneumonie" in all_results:
            return all_results["ira_pneumonie"]

    # Malnutrition : oedèmes + PB bas
    if symptomes.get("oedemes") and (symptomes.get("pb_mm", 130) or 130) < 115:
        if "malnutrition" in all_results:
            return all_results["malnutrition"]

    # Paludisme : fièvre + convulsions
    if symptomes.get("fievre") and symptomes.get("convulsions"):
        if "paludisme" in all_results:
            return all_results["paludisme"]

    # Défaut : premier résultat avec gravité max
    return candidates[0]


def _check_concordance(diag_arbre: str, diag_ml: str) -> bool:
    """
    Vérifie la concordance entre le diagnostic de l'arbre et celui du ML.

    Gère les cas où les deux diagnostics appartiennent à la même famille.
    """
    if diag_arbre == diag_ml:
        return True

    # Famille paludisme
    famille_paludisme = {"paludisme_grave", "paludisme_simple", "paludisme_peu_probable"}
    if diag_arbre in famille_paludisme and diag_ml in famille_paludisme:
        return True

    # Diagnostics indéterminés
    if diag_arbre in {"indetermine", "diagnostic_differentiel"}:
        return True

    return False


def _build_result(
    arbre: ResultatDiagnostic,
    ml: ProbabilitesDiagnostic,
    source: str,
    override_message: str = "",
    proba_override: float = None
) -> ResultatFinal:
    """Construit le ResultatFinal à partir des deux sources."""

    # Calcul de la probabilité combinée
    if proba_override is not None:
        proba_combinee = min(1.0, max(0.0, proba_override))
    elif source == "arbre":
        proba_combinee = 0.90 if arbre.gravite == 3 else 0.75
    else:
        proba_combinee = ml.top_1_probabilite * 0.60 + 0.40

    # Diagnostic différentiel (top 2 ML si différent du principal)
    diag_diff = None
    proba_diff = 0.0
    if ml.top_2_diagnostic and ml.top_2_probabilite > 0.20:
        if ml.top_2_diagnostic != arbre.diagnostic:
            diag_diff = ml.top_2_diagnostic
            proba_diff = ml.top_2_probabilite

    return ResultatFinal(
        diagnostic_principal=arbre.diagnostic,
        probabilite_combinee=round(proba_combinee, 3),
        gravite=arbre.gravite,
        couleur_alerte=arbre.couleur_alerte,
        action_immediate=arbre.action_immediate,
        recommandation_courte=arbre.recommandation_courte,
        recommandation_complete=arbre.recommandation_complete,
        traitement=arbre.traitement + arbre.traitement_pretransfert,
        contre_indications=arbre.contre_indications,
        structure_reference=arbre.structure_reference,
        notification_district=arbre.notification_district,
        diagnostic_differentiel=diag_diff,
        proba_differentiel=round(proba_diff, 3),
        source_decision=source,
        resultat_arbre=arbre,
        resultat_ml=ml,
        suivi=arbre.suivi
    )


def _arbre_only(arbre: ResultatDiagnostic, reason: str) -> ResultatFinal:
    """Construit un résultat en utilisant uniquement l'arbre décisionnel."""
    proba = 0.85 if arbre.gravite >= 2 else 0.65

    return ResultatFinal(
        diagnostic_principal=arbre.diagnostic,
        probabilite_combinee=proba,
        gravite=arbre.gravite,
        couleur_alerte=arbre.couleur_alerte,
        action_immediate=arbre.action_immediate,
        recommandation_courte=arbre.recommandation_courte,
        recommandation_complete=arbre.recommandation_complete,
        traitement=arbre.traitement + arbre.traitement_pretransfert,
        contre_indications=arbre.contre_indications,
        structure_reference=arbre.structure_reference,
        notification_district=arbre.notification_district,
        source_decision="arbre_seul",
        resultat_arbre=arbre,
        resultat_ml=None,
        suivi=arbre.suivi
    )
