"""
Simulation Cas 4 — Pneumonie Sévère Enfant
Patient : Garçon, 7 ans, 22 kg, Ngaoundéré Rural
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.decision_engine.aggregator import aggregate
from src.decision_engine.recommendation import generate_recommendation


def simulate_cas4():
    print("\n" + "="*60)
    print("CAS 4 — PNEUMONIE SÉVÈRE ENFANT")
    print("="*60)
    print("Patient : Garçon, 7 ans, 22 kg, Ngaoundéré Rural")
    print("Symptômes : Toux 4j, fièvre 38.9°C, tirage, FR=48/min, SpO2=91%")
    print("-"*60)

    symptomes = {
        "age_ans": 7,
        "poids_kg": 22,
        "sexe": 1,
        "toux": 1,
        "fievre": 1,
        "temperature_celsius": 38.9,
        "dyspnee": 1,
        "frequence_respiratoire": 48,
        "spo2_percent": 91,
        "duree_symptomes_jours": 4,
        "frissons": 0,
        "cephalee": 0,
        "vomissements": 0,
        "diarrhee": 0,
        "convulsions": 0,
        "trouble_conscience": 0,
        "grossesse": 0,
        "saison_pluie": 0,
        "zone_endemie_tb": 0
    }

    resultat = aggregate(symptomes)
    recommandation = generate_recommendation(resultat)

    print(f"\nRésultat diagnostic :")
    print(f"  Diagnostic          : {resultat.diagnostic_principal}")
    print(f"  Probabilité         : {resultat.probabilite_combinee*100:.1f}%")
    print(f"  Gravité             : {resultat.gravite}/3")
    print(f"  Couleur alerte      : {resultat.couleur_alerte}")
    print(f"  Transfert           : {recommandation.transfert}")

    print(f"\nRecommandation (résumé) :")
    for i, point in enumerate(recommandation.resume_3_points, 1):
        print(f"  {i}. {point}")

    # === ASSERTIONS CLINIQUES ===
    assert "ira" in resultat.diagnostic_principal or "pneumonie" in resultat.diagnostic_principal, \
        f"FAIL: diagnostic={resultat.diagnostic_principal}"
    print("\n✓ Diagnostic IRA/pneumonie confirmé")

    assert resultat.gravite == 3, f"FAIL: gravite={resultat.gravite}, attendu 3"
    print("✓ Gravité 3/3 confirmée (SpO2=91% → sévère)")

    assert resultat.couleur_alerte == "ROUGE", f"FAIL: couleur={resultat.couleur_alerte}"
    print("✓ Alerte ROUGE confirmée")

    assert recommandation.transfert["requis"] is True, "FAIL: transfert non requis"
    print("✓ Transfert requis confirmé")

    # Vérifier position semi-assise dans les recommandations
    rec_str = resultat.recommandation_complete.lower()
    resume_str = " ".join(recommandation.resume_3_points).lower()
    assert ("semi" in rec_str or "assise" in rec_str or "position" in rec_str or "transfert" in resume_str), \
        "FAIL: position semi-assise ou transfert absent"
    print("✓ Position semi-assise ou transfert mentionné")

    print(f"\n{'='*60}")
    print("CAS 4 : TOUTES LES ASSERTIONS PASSÉES ✓")
    print(f"{'='*60}")

    return {
        "cas": 4, "description": "Pneumonie sévère enfant",
        "diagnostic": resultat.diagnostic_principal, "gravite": resultat.gravite,
        "couleur": resultat.couleur_alerte, "transfert": recommandation.transfert,
        "resume": recommandation.resume_3_points, "passed": True
    }


if __name__ == "__main__":
    result = simulate_cas4()
    print(f"\nRésultat global : {'PASSÉ' if result['passed'] else 'ÉCHOUÉ'}")
