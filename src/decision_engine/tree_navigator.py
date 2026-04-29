"""
Moteur de navigation des arbres décisionnels pour HealthGuard IA.
Charge les arbres JSON et guide le parcours diagnostique.
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


# Chemin vers les arbres décisionnels
CLINICAL_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "clinical"

# Mapping code maladie -> fichier JSON
TREE_FILES = {
    "paludisme": "decision_tree_paludisme.json",
    "ira_pneumonie": "decision_tree_ira.json",
    "malnutrition": "decision_tree_malnutrition.json",
    "diarrhee_cholera": "decision_tree_diarrhee.json",
    "tuberculose": "decision_tree_tuberculose.json"
}


@dataclass
class ResultatDiagnostic:
    """Résultat final d'un parcours dans l'arbre décisionnel."""
    diagnostic: str
    gravite: int                     # 0=faible, 1=modéré, 2=élevé, 3=critique
    couleur_alerte: str              # VERT, ORANGE, ROUGE
    action_immediate: str
    recommandation_courte: str
    recommandation_complete: str
    traitement: list = field(default_factory=list)
    traitement_pretransfert: list = field(default_factory=list)
    contre_indications: list = field(default_factory=list)
    structure_reference: Optional[str] = None
    notification_district: bool = False
    chemin_parcouru: list = field(default_factory=list)
    maladie_testee: str = ""
    suivi: Optional[str] = None


def load_tree(maladie: str) -> dict:
    """
    Charge l'arbre décisionnel JSON pour une maladie donnée.

    Args:
        maladie: Code de la maladie (paludisme, ira_pneumonie, etc.)

    Returns:
        Dictionnaire représentant l'arbre décisionnel

    Raises:
        FileNotFoundError: Si le fichier JSON n'existe pas
        KeyError: Si la maladie n'est pas reconnue
    """
    if maladie not in TREE_FILES:
        raise KeyError(f"Maladie inconnue : '{maladie}'. Valides : {list(TREE_FILES.keys())}")

    tree_path = CLINICAL_DATA_PATH / TREE_FILES[maladie]
    if not tree_path.exists():
        raise FileNotFoundError(f"Fichier arbre introuvable : {tree_path}")

    with open(tree_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_next_question(noeud_id: str, tree: dict) -> Optional[dict]:
    """
    Retourne le noeud correspondant à un identifiant dans l'arbre.

    Args:
        noeud_id: Identifiant du noeud
        tree: Arbre décisionnel chargé

    Returns:
        Dictionnaire représentant le noeud, ou None si non trouvé
    """
    return tree.get("noeuds", {}).get(noeud_id)


def navigate(tree: dict, reponses: dict) -> ResultatDiagnostic:
    """
    Navigue dans l'arbre décisionnel selon les réponses fournies.

    La navigation utilise les réponses pré-fournies pour parcourir l'arbre
    automatiquement jusqu'à atteindre un noeud de type 'resultat'.

    Args:
        tree: Arbre décisionnel chargé via load_tree()
        reponses: Dictionnaire des réponses {noeud_id: valeur_reponse}
                  Valeurs : True/False pour questions, float pour mesures,
                  'oui'/'non', ou valeur numérique

    Returns:
        ResultatDiagnostic avec le diagnostic final et les recommandations
    """
    noeud_courant_id = tree["noeud_entree"]
    chemin = []
    noeuds = tree["noeuds"]
    maladie = tree.get("maladie", "inconnu")

    # Protection contre les boucles infinies
    max_iterations = 50
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        if noeud_courant_id not in noeuds:
            # Noeud non trouvé  retourner résultat d'erreur
            break

        noeud = noeuds[noeud_courant_id]
        chemin.append(noeud_courant_id)

        # Noeud de résultat final  on s'arrête
        if noeud["type"] == "resultat":
            return ResultatDiagnostic(
                diagnostic=noeud.get("diagnostic", "inconnu"),
                gravite=noeud.get("gravite", 0),
                couleur_alerte=noeud.get("couleur_alerte", "VERT"),
                action_immediate=noeud.get("action_immediate", ""),
                recommandation_courte=noeud.get("recommandation_courte", ""),
                recommandation_complete=noeud.get("recommandation_complete", ""),
                traitement=noeud.get("traitement", []),
                traitement_pretransfert=noeud.get("traitement_pretransfert", []),
                contre_indications=noeud.get("contre_indications", []),
                structure_reference=noeud.get("structure_reference"),
                notification_district=noeud.get("notification_district", False),
                chemin_parcouru=chemin,
                maladie_testee=maladie,
                suivi=noeud.get("suivi")
            )

        # Navigation selon le type de noeud
        noeud_suivant = _determine_next_node(noeud, reponses, noeud_courant_id)

        if noeud_suivant is None:
            # Aucune réponse disponible  résultat indéterminé
            break

        noeud_courant_id = noeud_suivant

    # Résultat par défaut si navigation impossible
    return ResultatDiagnostic(
        diagnostic="indetermine",
        gravite=1,
        couleur_alerte="ORANGE",
        action_immediate="EVALUATION_CLINIQUE",
        recommandation_courte="Données insuffisantes  Évaluation clinique complète nécessaire",
        recommandation_complete="Le système n'a pas pu atteindre un diagnostic avec les données fournies. Procéder à une évaluation clinique complète.",
        chemin_parcouru=chemin,
        maladie_testee=maladie
    )


def _determine_next_node(noeud: dict, reponses: dict, noeud_id: str) -> Optional[str]:
    """
    Détermine le prochain noeud selon les réponses disponibles.

    Args:
        noeud: Noeud courant
        reponses: Dictionnaire des réponses
        noeud_id: ID du noeud courant (pour accès à la réponse)

    Returns:
        ID du prochain noeud ou None
    """
    type_noeud = noeud["type"]
    reponse = reponses.get(noeud_id)

    if type_noeud == "question":
        if reponse is None:
            # Essayer avec la réponse 'oui' par défaut pour les cas sans données
            return noeud.get("reponse_non")

        # Normalisation de la réponse
        if isinstance(reponse, bool):
            est_oui = reponse
        elif isinstance(reponse, (int, float)):
            est_oui = bool(reponse)
        elif isinstance(reponse, str):
            est_oui = reponse.lower() in ('oui', 'yes', '1', 'true', 'vrai')
        else:
            est_oui = bool(reponse)

        return noeud.get("reponse_oui") if est_oui else noeud.get("reponse_non")

    elif type_noeud == "mesure":
        if reponse is None or reponse == "":
            return noeud.get("si_non_mesurable") or noeud.get("si_inferieur_ou_egal")

        try:
            valeur = float(reponse)
        except (ValueError, TypeError):
            return noeud.get("si_non_mesurable")

        # Gestion des différents seuils selon le noeud
        return _handle_mesure_node(noeud, valeur)

    elif type_noeud == "tranche_age":
        # Noeud de branchement par tranche d'âge
        return _handle_tranche_age(noeud, reponses)

    return None


def _handle_mesure_node(noeud: dict, valeur: float) -> Optional[str]:
    """Traite les noeuds de type mesure avec différents seuils."""

    # Gestion SpO2 avec seuils multiples
    if "seuil_critique" in noeud and "seuil_severe" in noeud:
        if valeur < noeud["seuil_critique"]:
            return noeud.get("si_inferieur_90")
        elif valeur < noeud["seuil_severe"]:
            return noeud.get("si_90_a_94")
        else:
            return noeud.get("si_superieur_ou_egal_95")

    # Gestion FR adulte avec deux seuils
    if "seuil_tachypnee_severe" in noeud:
        if valeur > noeud["seuil_tachypnee_severe"]:
            return noeud.get("si_superieur_30")
        elif valeur > noeud.get("seuil_tachypnee_legere", 20):
            return noeud.get("si_20_a_30")
        else:
            return noeud.get("si_inferieur_20")

    # Gestion tachypnée simple
    if "seuil_tachypnee" in noeud:
        if valeur > noeud["seuil_tachypnee"]:
            return noeud.get("si_superieur")
        else:
            return noeud.get("si_inferieur_ou_egal")

    # Gestion MAS/MAM (périmètre brachial)
    if "seuil_mas_enfant" in noeud:
        if valeur < noeud["seuil_mas_enfant"]:
            return noeud.get("si_inferieur_115")
        elif valeur < noeud["seuil_mam_enfant"]:
            return noeud.get("si_115_a_125")
        else:
            return noeud.get("si_superieur_125")

    # Gestion standard avec seuil positif
    if "seuil_positif" in noeud:
        if valeur >= noeud["seuil_positif"]:
            return noeud.get("si_superieur_ou_egal") or noeud.get("si_superieur")
        else:
            return noeud.get("si_inferieur")

    # Seuil générique
    if "seuil_suspect" in noeud:
        if valeur >= noeud["seuil_suspect"]:
            return noeud.get("si_superieur_ou_egal_3") or noeud.get("si_superieur_ou_egal")
        else:
            return noeud.get("si_inferieur_3") or noeud.get("si_inferieur")

    if "seuil_diarrhee" in noeud:
        if valeur >= noeud["seuil_diarrhee"]:
            return noeud.get("si_superieur_ou_egal_3")
        else:
            return noeud.get("si_inferieur_3")

    return noeud.get("si_non_mesurable")


def _handle_tranche_age(noeud: dict, reponses: dict) -> Optional[str]:
    """Gère les noeuds de branchement par tranche d'âge."""
    # Chercher l'âge dans les réponses
    age = None
    for key in reponses:
        if 'age' in key.lower() or key == 'age_ans':
            age = reponses[key]
            break

    if age is None:
        return noeud.get("reponse_plus_5_ans")  # Adulte par défaut

    try:
        age = float(age)
    except (ValueError, TypeError):
        return noeud.get("reponse_plus_5_ans")

    if age < 2/12:  # < 2 mois
        return noeud.get("reponse_moins_2_mois")
    elif age < 1:   # 2-12 mois
        return noeud.get("reponse_2_a_12_mois")
    elif age <= 5:  # 1-5 ans
        return noeud.get("reponse_1_a_5_ans")
    else:           # > 5 ans
        return noeud.get("reponse_plus_5_ans")


def navigate_all_trees(symptomes: dict) -> list:
    """
    Navigue dans tous les arbres décisionnels et retourne les résultats triés par gravité.

    Chaque arbre reçoit son propre mapping de réponses pour éviter les conflits
    entre arbres qui partagent les mêmes identifiants de noeuds (ex: "N2").

    Args:
        symptomes: Dictionnaire des symptômes et valeurs mesurées

    Returns:
        Liste de ResultatDiagnostic triée par gravité décroissante
    """
    resultats = []

    for maladie in TREE_FILES.keys():
        try:
            tree = load_tree(maladie)
            reponses = _symptomes_to_reponses_for_tree(symptomes, maladie)
            resultat = navigate(tree, reponses)
            resultat.maladie_testee = maladie
            resultats.append(resultat)
        except Exception:
            continue

    # Tri par gravité décroissante
    resultats.sort(key=lambda r: r.gravite, reverse=True)
    return resultats


def _symptomes_to_reponses_for_tree(symptomes: dict, maladie: str) -> dict:
    """Retourne les réponses spécifiques à l'arbre demandé."""
    if maladie == "paludisme":
        return _reponses_paludisme(symptomes)
    elif maladie == "ira_pneumonie":
        return _reponses_ira(symptomes)
    elif maladie == "malnutrition":
        return _reponses_malnutrition(symptomes)
    elif maladie == "diarrhee_cholera":
        return _reponses_diarrhee(symptomes)
    elif maladie == "tuberculose":
        return _reponses_tuberculose(symptomes)
    return _symptomes_to_reponses(symptomes)


def _reponses_paludisme(s: dict) -> dict:
    # N4 = signes de gravité STRICTS : convulsions OU trouble conscience
    # Les vomissements seuls ne suffisent pas pour ROUGE (ils sont gérés en N6)
    signes_gravite_stricts = bool(s.get("convulsions", 0)) or bool(s.get("trouble_conscience", 0))
    return {
        "N1": bool(s.get("fievre", 0)),
        "N2": s.get("temperature_celsius", 37.0),
        "N3": (s.get("age_ans", 99) < 5) or bool(s.get("grossesse", 0)),
        "N3_ATTENUATION": (s.get("age_ans", 99) < 5) or bool(s.get("grossesse", 0)),
        "N4": signes_gravite_stricts,
        "N4B": True,
        "N5": bool(s.get("cephalee", 0)) and bool(s.get("frissons", 0)),
        "N5_FAIBLE": bool(s.get("cephalee", 0)) and bool(s.get("frissons", 0)),
        "N6": bool(s.get("vomissements", 0)),
        "N6B": s.get("duree_symptomes_jours", 0) > 5,
        "N6_INCERTAIN": bool(s.get("saison_pluie", 0)),
    }


def _reponses_ira(s: dict) -> dict:
    fr = s.get("frequence_respiratoire", 0) or 0
    age = s.get("age_ans", 30) or 30
    spo2 = s.get("spo2_percent", None)
    tirage = bool(s.get("dyspnee", 0)) and fr > 0 and (
        (age < 2/12 and fr > 60) or (age < 1 and fr > 50) or
        (age <= 5 and fr > 40) or (age > 5 and fr > 30)
    )
    return {
        "N1": bool(s.get("toux", 0)) or bool(s.get("dyspnee", 0)),
        "N2": bool(s.get("fievre", 0)),
        "N3": tirage,
        "N3_SANS_FIEVRE": tirage,
        "N4": spo2 is not None and spo2 < 95,
        "N4B_SPO2": spo2 if spo2 is not None else 100,
        "N4_SANS_FIEVRE": spo2 is not None and spo2 < 95,
        "N5A_2MOIS": fr, "N5B_12MOIS": fr, "N5C_5ANS": fr, "N5D_ADULTE": fr,
        "N6_GRAVITE": spo2 is not None and spo2 < 90,
        "N6_SIGNES_GENERAUX": s.get("duree_symptomes_jours", 0) > 5,
    }


def _reponses_malnutrition(s: dict) -> dict:
    age = s.get("age_ans", 30) or 30
    pb = s.get("pb_mm", s.get("muac_mm", 130)) or 130
    return {
        "N1": (age < 5) or bool(s.get("grossesse", 0)),
        "N1B_ADULTE": bool(s.get("oedemes", 0)),
        "N2": pb,
        "N3_MAS": bool(s.get("oedemes", 0)),
        "N3_MAM": bool(s.get("oedemes", 0)),
        "N4_OEDEMES_CHECK": bool(s.get("oedemes", 0)),
        "N3_ADULTE": bool(s.get("oedemes", 0)),
        "N4_COMPLICATIONS": bool(s.get("fievre", 0)) and (s.get("temperature_celsius", 37) or 37) >= 38.5,
        "N5_TEST_APPETIT": not bool(s.get("fievre", 0)) and not bool(s.get("vomissements", 0)),
        "N5_MAM_SANS_COMPLICATION": bool(s.get("fievre", 0)),
    }


def _reponses_diarrhee(s: dict) -> dict:
    nb_selles = s.get("selles_par_jour", 5 if s.get("diarrhee") else 1) or 1
    return {
        "N1": nb_selles,
        "N2": bool(s.get("epidemie_cholera_active", 0)),
        "N3_CHOLERA": bool(s.get("signes_deshydratation_severes", 0)),
        "N3_DIARRHEE_SIMPLE": bool(s.get("signes_deshydratation_severes", 0)),
        "N4_CHOLERA_MODERE": bool(s.get("grossesse", 0)),
        "N5_SIGNES_MODERES_CHOLERA": bool(s.get("vomissements", 0)) and bool(s.get("diarrhee", 0)),
        "N4_DESHYDRATATION_SEVERE": bool(s.get("grossesse", 0)),
        "N4_DESHYDRATATION_MODEREE": bool(s.get("vomissements", 0)),
        "N5_DIARRHEE_SEVERE": bool(s.get("fievre", 0)),
        "N5_DIARRHEE_MODEREE": bool(s.get("fievre", 0)),
        "N6_FIEVRE": bool(s.get("fievre", 0)),
        "N7_DUREE": s.get("duree_symptomes_jours", 0) > 7,
    }


def _reponses_tuberculose(s: dict) -> dict:
    duree_semaines = (s.get("duree_symptomes_jours", 0) or 0) / 7
    return {
        "N1": duree_semaines,
        "N1B": bool(s.get("hemoptysie", 0)),
        "N2": True,  # Amaigrissement  supposé si durée longue
        "N3": True,  # Sueurs nocturnes  supposé si toux prolongée
        "N4": bool(s.get("contact_tb_connu", 0)),
        "N4_SANS_SUEURS": bool(s.get("contact_tb_connu", 0)),
        "N4_MODERE": bool(s.get("contact_tb_connu", 0)) or bool(s.get("zone_endemie_tb", 0)),
        "N4_SANS_SIGNES": bool(s.get("contact_tb_connu", 0)) and bool(s.get("hemoptysie", 0)),
        "N5_SANS_CONTACT": bool(s.get("zone_endemie_tb", 0)),
        "N5_GRAVITE": bool(s.get("dyspnee", 0)) and (s.get("spo2_percent", 100) or 100) < 90,
    }


def _symptomes_to_reponses(symptomes: dict) -> dict:
    """
    Convertit le dictionnaire de symptômes en réponses pour les noeuds d'arbre.

    Mappe les noms de features du modèle ML vers les noeuds des arbres.

    Args:
        symptomes: Dictionnaire de symptômes (features ML)

    Returns:
        Dictionnaire réponses mappées aux noeuds des arbres
    """
    reponses = {}

    # Mapping paludisme
    reponses["N1"] = bool(symptomes.get("fievre", 0))
    reponses["N2"] = symptomes.get("temperature_celsius", 37.0)
    reponses["N3"] = (symptomes.get("age_ans", 99) < 5) or bool(symptomes.get("grossesse", 0))
    reponses["N3_ATTENUATION"] = (symptomes.get("age_ans", 99) < 5) or bool(symptomes.get("grossesse", 0))
    reponses["N4"] = bool(symptomes.get("convulsions", 0)) or bool(symptomes.get("trouble_conscience", 0)) or bool(symptomes.get("vomissements", 0))
    reponses["N4B"] = True  # TDR non disponible par défaut
    reponses["N5"] = bool(symptomes.get("cephalee", 0)) and bool(symptomes.get("frissons", 0))
    reponses["N5_FAIBLE"] = bool(symptomes.get("cephalee", 0)) and bool(symptomes.get("frissons", 0))
    reponses["N6"] = bool(symptomes.get("vomissements", 0))
    reponses["N6B"] = symptomes.get("duree_symptomes_jours", 0) > 5
    reponses["N6_INCERTAIN"] = bool(symptomes.get("saison_pluie", 0)) or bool(symptomes.get("zone_endemie_tb", 0))

    # Mapping IRA
    reponses["N1_IRA"] = bool(symptomes.get("toux", 0)) or bool(symptomes.get("dyspnee", 0))
    reponses["N2_IRA"] = bool(symptomes.get("fievre", 0))

    # Noeud IRA N3 = tirage sous-costal (pas de feature directe, on l'approxime avec FR et SpO2)
    fr = symptomes.get("frequence_respiratoire", 0)
    age = symptomes.get("age_ans", 99)
    spo2 = symptomes.get("spo2_percent", 100)

    # Tirage approximé par sévérité des symptômes respiratoires
    tirage_estime = (fr > 50 and age < 1) or (fr > 40 and age <= 5) or (fr > 30 and age > 5) or (spo2 < 90)
    reponses["N3"] = tirage_estime or bool(symptomes.get("dyspnee", 0))
    reponses["N3_SANS_FIEVRE"] = tirage_estime

    reponses["N4"] = spo2 < 95 if spo2 else False
    reponses["N4B_SPO2"] = spo2 if spo2 else 100
    reponses["N4_SANS_FIEVRE"] = spo2 < 95 if spo2 else False

    # Fréquences respiratoires selon âge
    for noeud_fr in ["N5A_2MOIS", "N5B_12MOIS", "N5C_5ANS", "N5D_ADULTE"]:
        reponses[noeud_fr] = fr if fr else 0

    reponses["N6_GRAVITE"] = spo2 < 90 if spo2 else False
    reponses["N6_SIGNES_GENERAUX"] = symptomes.get("duree_symptomes_jours", 0) > 5

    # Mapping malnutrition
    pb = symptomes.get("pb_mm", symptomes.get("muac_mm", 130))
    reponses["N1_MAL"] = (age < 5) or bool(symptomes.get("grossesse", 0))
    reponses["N2_MAL"] = pb
    reponses["N3_MAS"] = bool(symptomes.get("oedemes", 0))
    reponses["N3_MAM"] = bool(symptomes.get("oedemes", 0))
    reponses["N4_OEDEMES_CHECK"] = bool(symptomes.get("oedemes", 0))
    reponses["N4_COMPLICATIONS"] = bool(symptomes.get("fievre", 0)) and symptomes.get("temperature_celsius", 37) >= 38.5

    # Test appétit approximé
    reponses["N5_TEST_APPETIT"] = True  # Par défaut, test positif si pas de fièvre
    if bool(symptomes.get("fievre", 0)):
        reponses["N5_TEST_APPETIT"] = False

    # Mapping diarrhée/choléra
    nb_selles = symptomes.get("selles_par_jour", 5 if symptomes.get("diarrhee") else 0)
    reponses["N1_DIAR"] = nb_selles
    reponses["N2_DIAR"] = bool(symptomes.get("epidemie_cholera_active", 0))
    reponses["N3_CHOLERA"] = bool(symptomes.get("signes_deshydratation_severes", 0))
    reponses["N3_DIARRHEE_SIMPLE"] = bool(symptomes.get("signes_deshydratation_severes", 0))
    reponses["N4_CHOLERA_MODERE"] = bool(symptomes.get("grossesse", 0))
    reponses["N5_SIGNES_MODERES_CHOLERA"] = bool(symptomes.get("vomissements", 0)) and bool(symptomes.get("diarrhee", 0))
    reponses["N4_DESHYDRATATION_SEVERE"] = bool(symptomes.get("grossesse", 0))
    reponses["N4_DESHYDRATATION_MODEREE"] = bool(symptomes.get("vomissements", 0))
    reponses["N5_DIARRHEE_SEVERE"] = bool(symptomes.get("fievre", 0))
    reponses["N5_DIARRHEE_MODEREE"] = bool(symptomes.get("fievre", 0))
    reponses["N6_FIEVRE"] = bool(symptomes.get("fievre", 0))
    reponses["N7_DUREE"] = symptomes.get("duree_symptomes_jours", 0) > 7

    # Mapping tuberculose
    duree_semaines = symptomes.get("duree_symptomes_jours", 0) / 7
    reponses["N1_TB"] = duree_semaines
    reponses["N1B"] = bool(symptomes.get("hemoptysie", 0))
    reponses["N2_TB"] = True  # Amaigrissement approximé
    reponses["N3_TB"] = True  # Sueurs nocturnes  défaut à vrai si toux prolongée
    reponses["N4_TB"] = bool(symptomes.get("contact_tb_connu", 0))
    reponses["N4_SANS_SUEURS"] = bool(symptomes.get("contact_tb_connu", 0))
    reponses["N5_SANS_CONTACT"] = bool(symptomes.get("zone_endemie_tb", 0))
    reponses["N5_GRAVITE"] = bool(symptomes.get("dyspnee", 0)) and symptomes.get("spo2_percent", 100) < 90

    return reponses
