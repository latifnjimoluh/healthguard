"""
Module de scoring de gravité pour HealthGuard IA.
Calcule un score de gravité 0-3 basé sur les symptômes vitaux et les signes cliniques.
"""

from typing import Optional


def calculate_severity_score(symptomes: dict) -> dict:
    """
    Calcule le score de gravité basé sur les paramètres vitaux.

    Système de scoring additionnel aux arbres décisionnels,
    basé sur les signes vitaux et signes d'alarme.

    Args:
        symptomes: Dictionnaire de symptômes et mesures

    Returns:
        dict {score, niveau, couleur, signes_alarme, justification}
    """
    score_points = 0
    signes_alarme = []

    # --- Signes d'alarme critiques (3 points chacun) ---

    # Troubles neurologiques
    if symptomes.get("convulsions"):
        score_points += 3
        signes_alarme.append("Convulsions présentes")

    if symptomes.get("trouble_conscience"):
        score_points += 3
        signes_alarme.append("Trouble de conscience")

    # Détresse respiratoire sévère
    spo2 = symptomes.get("spo2_percent")
    if spo2 is not None and spo2 < 90:
        score_points += 3
        signes_alarme.append(f"SpO2 critique : {spo2}%")

    # --- Signes d'alarme importants (2 points chacun) ---

    # Fièvre très élevée
    temp = symptomes.get("temperature_celsius", 37.0)
    if temp >= 40.0:
        score_points += 2
        signes_alarme.append(f"Hyperthermie : {temp}°C")
    elif temp >= 39.5:
        score_points += 1

    # SpO2 anormale (mais pas critique)
    if spo2 is not None and 90 <= spo2 < 95:
        score_points += 2
        signes_alarme.append(f"SpO2 basse : {spo2}%")

    # Tachypnée sévère selon âge
    fr = symptomes.get("frequence_respiratoire", 18)
    age = symptomes.get("age_ans", 30)
    if fr:
        tachypnee_severe = _is_severe_tachypnee(fr, age)
        if tachypnee_severe:
            score_points += 2
            signes_alarme.append(f"Tachypnée sévère : {fr}/min")

    # Déshydratation sévère
    if symptomes.get("signes_deshydratation_severes"):
        score_points += 2
        signes_alarme.append("Déshydratation sévère")

    # --- Signes modérés (1 point chacun) ---

    # Vomissements répétés
    if symptomes.get("vomissements"):
        score_points += 1

    # Dyspnée
    if symptomes.get("dyspnee"):
        score_points += 1

    # Hémoptysie
    if symptomes.get("hemoptysie"):
        score_points += 1

    # Œdèmes (malnutrition)
    if symptomes.get("oedemes"):
        score_points += 1

    # Durée longue
    duree = symptomes.get("duree_symptomes_jours", 1)
    if duree > 7:
        score_points += 1

    # Groupe vulnérable
    age = symptomes.get("age_ans", 30)
    grossesse = symptomes.get("grossesse", 0)
    if age < 5 or (grossesse and isinstance(grossesse, (int, float)) and grossesse > 0):
        score_points += 1
        signes_alarme.append("Groupe vulnérable (enfant <5 ans ou femme enceinte)")

    # --- Calcul du score final (0-3) ---
    if score_points >= 6:
        score = 3
        niveau = "CRITIQUE"
        couleur = "ROUGE"
    elif score_points >= 3:
        score = 2
        niveau = "ÉLEVÉ"
        couleur = "ORANGE"
    elif score_points >= 1:
        score = 1
        niveau = "MODÉRÉ"
        couleur = "ORANGE"
    else:
        score = 0
        niveau = "FAIBLE"
        couleur = "VERT"

    return {
        "score": score,
        "score_brut": score_points,
        "niveau": niveau,
        "couleur": couleur,
        "signes_alarme": signes_alarme,
        "justification": f"Score brut : {score_points} points basé sur {len(signes_alarme)} signe(s) d'alarme"
    }


def _is_severe_tachypnee(fr: float, age_ans: float) -> bool:
    """
    Vérifie si la fréquence respiratoire est en zone de tachypnée sévère selon l'âge.
    Seuils OMS PCIME/IMCI.
    """
    if age_ans < 2/12:   # < 2 mois
        return fr > 70
    elif age_ans < 1:    # 2-12 mois
        return fr > 60
    elif age_ans <= 5:   # 1-5 ans
        return fr > 50
    else:                # > 5 ans / adulte
        return fr > 30
