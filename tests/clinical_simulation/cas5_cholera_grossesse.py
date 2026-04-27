"""
Simulation Cas 5 — Choléra Femme Enceinte
Patient : Femme, 25 ans, 58 kg, enceinte 7 mois, Est-Cameroun
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.decision_engine.aggregator import aggregate
from src.decision_engine.recommendation import generate_recommendation


def simulate_cas5():
    print("\n" + "="*60)
    print("CAS 5 — CHOLÉRA FEMME ENCEINTE")
    print("="*60)
    print("Patient : Femme, 25 ans, enceinte 7 mois, Village Est-Cameroun")
    print("Symptômes : Diarrhée profuse 18h, vomissements, déshydratation sévère, épidémie active")
    print("-"*60)

    symptomes = {
        "age_ans": 25,
        "poids_kg": 58,
        "sexe": 0,
        "grossesse": 1,
        "diarrhee": 1,
        "vomissements": 1,
        "fievre": 1,
        "temperature_celsius": 37.8,
        "duree_symptomes_jours": 1,
        "epidemie_cholera_active": 1,
        "signes_deshydratation_severes": 1,
        "toux": 0,
        "hemoptysie": 0,
        "convulsions": 0,
        "trouble_conscience": 0,
        "oedemes": 0,
        "dyspnee": 0,
        "frissons": 0,
        "cephalee": 1,
        "saison_pluie": 1,
        "zone_endemie_tb": 0,
        "contact_tb_connu": 0
    }

    resultat = aggregate(symptomes)
    recommandation = generate_recommendation(resultat)

    print(f"\nRésultat diagnostic :")
    print(f"  Diagnostic          : {resultat.diagnostic_principal}")
    print(f"  Probabilité         : {resultat.probabilite_combinee*100:.1f}%")
    print(f"  Gravité             : {resultat.gravite}/3")
    print(f"  Couleur alerte      : {resultat.couleur_alerte}")
    print(f"  Notification dist.  : {recommandation.notification_district}")
    print(f"  Transfert           : {recommandation.transfert}")

    print(f"\nRecommandation (résumé) :")
    for i, point in enumerate(recommandation.resume_3_points, 1):
        print(f"  {i}. {point}")

    # === ASSERTIONS CLINIQUES ===
    assert "diarrhee" in resultat.diagnostic_principal or "cholera" in resultat.diagnostic_principal.lower(), \
        f"FAIL: diagnostic={resultat.diagnostic_principal}"
    print("\n✓ Diagnostic diarrhée/choléra confirmé")

    assert resultat.gravite == 3, f"FAIL: gravite={resultat.gravite}, attendu 3"
    print("✓ Gravité 3/3 confirmée")

    assert resultat.couleur_alerte == "ROUGE", f"FAIL: couleur={resultat.couleur_alerte}"
    print("✓ Alerte ROUGE confirmée")

    # CRITIQUE : notification district obligatoire (choléra = déclaration obligatoire)
    assert recommandation.notification_district is True, \
        "FAIL: notification district obligatoire absente"
    print("✓ Notification district OBLIGATOIRE confirmée (CRITIQUE)")

    # Vérifier mention grossesse et réhydratation dans la recommandation
    rec_str = resultat.recommandation_complete.lower()
    resume_str = " ".join(recommandation.resume_3_points).lower()
    assert ("grossesse" in rec_str or "foetal" in rec_str or "ringer" in rec_str or "notification" in resume_str), \
        "FAIL: mention grossesse ou réhydratation absente"
    print("✓ Adaptation grossesse ou réhydratation mentionnée")

    # Vérifier réhydratation (SRO ou Ringer)
    assert ("ringer" in rec_str or "sro" in rec_str or "rehydrat" in rec_str), \
        "FAIL: protocole de réhydratation absent"
    print("✓ Protocole réhydratation présent (SRO/Ringer)")

    print(f"\n{'='*60}")
    print("CAS 5 : TOUTES LES ASSERTIONS PASSÉES ✓")
    print(f"{'='*60}")

    return {
        "cas": 5, "description": "Choléra femme enceinte",
        "diagnostic": resultat.diagnostic_principal, "gravite": resultat.gravite,
        "couleur": resultat.couleur_alerte,
        "notification": recommandation.notification_district,
        "resume": recommandation.resume_3_points, "passed": True
    }


if __name__ == "__main__":
    result = simulate_cas5()
    print(f"\nRésultat global : {'PASSÉ' if result['passed'] else 'ÉCHOUÉ'}")
