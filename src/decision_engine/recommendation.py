"""
Générateur de recommandations structurées pour HealthGuard IA.
Mappe le résultat du moteur de décision vers des recommandations cliniques.
"""

from typing import Optional
from dataclasses import dataclass, field
from src.decision_engine.aggregator import ResultatFinal


@dataclass
class Recommandation:
    """Recommandation clinique structurée, version courte et longue."""
    couleur_alerte: str                    # ROUGE, ORANGE, VERT
    action_immediate: str                  # Action prioritaire
    resume_3_points: list                  # Version courte (mode stress)
    detail_complet: str                    # Version longue
    medicaments: list                      # [{nom, dose, duree, voie}]
    contre_indications: list               # Contre-indications
    suivi_recommande: Optional[str]        # J3, J7, J14, AUCUN
    transfert: dict                        # {requis, structure, urgence}
    notification_district: bool            # Maladie à déclaration obligatoire
    diagnostic_differentiel: Optional[str] = None
    proba_differentiel: float = 0.0


# Base de données des médicaments par maladie
MEDICAMENTS_DB = {
    "artemether_lumefantrine": {
        "nom": "Artéméther-Luméfantrine (AL / Coartem)",
        "dose_adulte": "4 comprimés × 2/jour × 3 jours (avec nourriture)",
        "dose_enfant": "Selon poids : 5-14kg → 1cp; 15-24kg → 2cp; 25-34kg → 3cp",
        "voie": "orale",
        "duree": 3,
        "notes": "Prendre avec nourriture ou lait pour améliorer absorption"
    },
    "artemether_lumefantrine_selon_poids": {
        "nom": "Artéméther-Luméfantrine (AL)  dose poids-dépendante",
        "dose_adulte": "4 comprimés × 2/jour × 3 jours",
        "dose_enfant": "5-14kg: 1cp; 15-24kg: 2cp; 25-34kg: 3cp; >34kg: 4cp",
        "voie": "orale",
        "duree": 3,
        "notes": "Enfant < 5kg : non recommandé. Grossesse T1 : quinine préférable"
    },
    "quinine_iv": {
        "nom": "Quinine IV (pré-transfert paludisme grave)",
        "dose_adulte": "20mg/kg en 4h (dose charge), puis 10mg/kg/8h",
        "dose_enfant": "20mg/kg en 4h (dose charge), puis 10mg/kg/8h",
        "voie": "intraveineuse",
        "duree": None,
        "notes": "UNIQUEMENT si voie IV disponible. Ne pas dépasser 1800mg/j adulte"
    },
    "amoxicilline_orale": {
        "nom": "Amoxicilline orale",
        "dose_adulte": "1g × 3/jour × 7 jours",
        "dose_enfant": "40-45mg/kg/jour en 2 prises × 5 jours",
        "voie": "orale",
        "duree": 5,
        "notes": "Prendre à heure fixe. Compléter le traitement même si amélioration"
    },
    "amoxicilline_im": {
        "nom": "Amoxicilline IM (pré-transfert pneumonie sévère)",
        "dose_adulte": "1g IM dose unique avant transfert",
        "dose_enfant": "50mg/kg IM dose unique",
        "voie": "intramusculaire",
        "duree": None,
        "notes": "Dose unique avant transfert uniquement"
    },
    "SRO": {
        "nom": "Sels de Réhydratation Orale (SRO)",
        "dose_adulte": "Plan A : 200-400ml après chaque selle. Plan B : 75ml/kg sur 4h",
        "dose_enfant": "Plan A : 100-200ml après chaque selle. Plan B : 75ml/kg sur 4h",
        "voie": "orale",
        "duree": None,
        "notes": "Préparer avec eau propre. Jeter si non consommé après 24h"
    },
    "Ringer_Lactate_IV": {
        "nom": "Ringer Lactate IV (réhydratation sévère)",
        "dose_adulte": "100ml/kg en 3h (adulte)",
        "dose_enfant": "100ml/kg en 3h (ou 30ml/kg en 30min si choc)",
        "voie": "intraveineuse",
        "duree": None,
        "notes": "Grossesse : adapter la vitesse selon surveillance foetale"
    },
    "ATPE_Plumpy_Nut": {
        "nom": "ATPE  Plumpy'Nut (Aliment Thérapeutique Prêt à l'Emploi)",
        "dose_adulte": "N/A (produit pédiatrique)",
        "dose_enfant": "92g/kg/semaine (environ 3-4 sachets/jour selon poids)",
        "voie": "orale",
        "duree": 56,
        "notes": "NE PAS mélanger à de l'eau. Ne pas partager. Conserver au frais"
    },
    "doxycycline": {
        "nom": "Doxycycline (choléra)",
        "dose_adulte": "300mg dose unique",
        "dose_enfant": "Non recommandé < 8 ans",
        "voie": "orale",
        "duree": 1,
        "notes": "CONTRE-INDIQUÉE grossesse → Azithromycine à la place"
    }
}


def generate_recommendation(resultat: ResultatFinal) -> Recommandation:
    """
    Génère une recommandation structurée à partir du résultat du moteur de décision.

    Args:
        resultat: ResultatFinal de l'agrégateur

    Returns:
        Recommandation avec version courte (3 points) et version longue
    """
    # Construction du résumé 3 points (mode stress)
    resume = _build_resume_3_points(resultat)

    # Construction des informations de transfert
    transfert = _build_transfert_info(resultat)

    # Construction de la liste des médicaments
    medicaments = _build_medicaments_list(resultat)

    return Recommandation(
        couleur_alerte=resultat.couleur_alerte,
        action_immediate=resultat.action_immediate,
        resume_3_points=resume,
        detail_complet=resultat.recommandation_complete,
        medicaments=medicaments,
        contre_indications=resultat.contre_indications,
        suivi_recommande=resultat.suivi,
        transfert=transfert,
        notification_district=resultat.notification_district,
        diagnostic_differentiel=resultat.diagnostic_differentiel,
        proba_differentiel=resultat.proba_differentiel
    )


def _build_resume_3_points(resultat: ResultatFinal) -> list:
    """Construit un résumé en 3 points maximum pour mode urgence."""
    points = []

    # Point 1 : Action immédiate
    if resultat.gravite == 3:
        points.append(f"🔴 TRANSFERT IMMÉDIAT  {resultat.structure_reference or 'CMA district'}")
    elif resultat.gravite == 2:
        points.append(f"🟠 Traitement local + surveillance rapprochée")
    else:
        points.append(f"🟢 Traitement ambulatoire  Revenir si aggravation")

    # Point 2 : Action médicale principale
    diag = resultat.diagnostic_principal
    if "paludisme_grave" in diag:
        points.append("Quinine IV si disponible  NE PAS donner AL oral")
    elif "paludisme" in diag:
        points.append("Artéméther-Luméfantrine (AL)  dose selon poids")
    elif "ira" in diag or "pneumonie" in diag:
        if resultat.gravite >= 3:
            points.append("Amoxicilline IM + position semi-assise + O2 si dispo")
        else:
            points.append("Amoxicilline orale 5 jours  surveiller FR")
    elif "malnutrition" in diag:
        points.append("ATPE Plumpy'Nut selon poids  Test appétit obligatoire")
    elif "diarrhee" in diag or "cholera" in diag:
        if resultat.gravite >= 3:
            points.append("Ringer Lactate IV  NOTIFICATION district si choléra")
        else:
            points.append("SRO plan B (75ml/kg/4h)  Surveiller diurèse")
    elif "tuberculose" in diag:
        points.append("NE PAS donner antibiotiques  Référence CDTB obligatoire")
    else:
        points.append("Évaluation clinique complète  Traitement symptomatique")

    # Point 3 : Surveillance ou contre-indication critique
    if resultat.contre_indications:
        ci = resultat.contre_indications[0]
        ci_labels = {
            "artemether_lumefantrine_oral": "⚠️ CONTRE-INDICATION : AL oral interdit",
            "antibiotiques_empiriques": "⚠️ CONTRE-INDICATION : Pas d'antibiotiques empiriques TB",
            "doxycycline_grossesse": "⚠️ GROSSESSE : Azithromycine à la place de Doxycycline"
        }
        points.append(ci_labels.get(ci, f"⚠️ {ci}"))
    elif resultat.notification_district:
        points.append("📢 NOTIFICATION DISTRICT OBLIGATOIRE (maladie à déclaration)")
    elif resultat.suivi:
        suivi_labels = {
            "J3_obligatoire": "Consultation de suivi OBLIGATOIRE à J3",
            "J3_si_persistance": "Revenir à J3 si fièvre persiste",
            "J7": "Consultation de suivi à J7"
        }
        points.append(suivi_labels.get(resultat.suivi, f"Suivi : {resultat.suivi}"))

    return points[:3]  # Maximum 3 points


def _build_transfert_info(resultat: ResultatFinal) -> dict:
    """Construit les informations de transfert."""
    if resultat.gravite == 3:
        return {
            "requis": True,
            "structure": resultat.structure_reference or "CMA de district",
            "urgence": "IMMÉDIAT (< 1 heure)"
        }
    elif resultat.gravite == 2 and resultat.structure_reference:
        return {
            "requis": True,
            "structure": resultat.structure_reference,
            "urgence": "Dans les 24 heures"
        }
    else:
        return {
            "requis": False,
            "structure": None,
            "urgence": None
        }


def _build_medicaments_list(resultat: ResultatFinal) -> list:
    """Construit la liste des médicaments avec dosages."""
    medicaments = []

    for med_code in (resultat.traitement or []):
        if med_code in MEDICAMENTS_DB:
            medicaments.append(MEDICAMENTS_DB[med_code])
        else:
            # Médicament non trouvé dans la DB
            medicaments.append({"nom": med_code, "dose_adulte": "Voir protocole", "voie": "?"})

    return medicaments
