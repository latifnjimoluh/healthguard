"""
Simulation Cas 2  Malnutrition Aiguë Sévère
Patient : Fille, 18 mois, Village Batouri, Est-Cameroun
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.decision_engine.aggregator import aggregate
from src.decision_engine.recommendation import generate_recommendation


def simulate_cas2():
    print("\n" + "="*60)
    print("CAS 2  MALNUTRITION AIGUË SÉVÈRE")
    print("="*60)
    print("Patient : Fille, 18 mois, Village Batouri, Est-Cameroun")
    print("Symptômes : PB 108mm, oedèmes aux pieds, appétit réduit 3 semaines")
    print("-"*60)

    symptomes = {
        "age_ans": 1.5,
        "poids_kg": 7.2,
        "sexe": 0,
        "fievre": 0,
        "temperature_celsius": 36.8,
        "oedemes": 1,
        "duree_symptomes_jours": 21,
        "pb_mm": 108,
        "muac_mm": 108,
        "toux": 0,
        "diarrhee": 0,
        "vomissements": 0,
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
    assert "malnutrition" in resultat.diagnostic_principal, \
        f"FAIL: diagnostic={resultat.diagnostic_principal}"
    print("\n✓ Diagnostic malnutrition confirmé")

    assert resultat.gravite >= 2, f"FAIL: gravite={resultat.gravite}, attendu >= 2"
    print("✓ Gravité >= 2 confirmée")

    assert resultat.couleur_alerte in ("ORANGE", "ROUGE"), \
        f"FAIL: couleur={resultat.couleur_alerte}"
    print("✓ Alerte ORANGE/ROUGE confirmée")

    # Vérifier présence ATPE dans les traitements
    traitements_str = str(resultat.traitement).upper()
    detail_str = resultat.recommandation_complete.upper()
    assert any(mot in traitements_str or mot in detail_str
               for mot in ["ATPE", "PLUMPY", "NUT"]), \
        "FAIL: ATPE/Plumpy'Nut absent des recommandations"
    print("✓ ATPE Plumpy'Nut mentionné")

    print(f"\n{'='*60}")
    print("CAS 2 : TOUTES LES ASSERTIONS PASSÉES ✓")
    print(f"{'='*60}")

    return {
        "cas": 2, "description": "Malnutrition aiguë sévère",
        "diagnostic": resultat.diagnostic_principal, "gravite": resultat.gravite,
        "couleur": resultat.couleur_alerte, "transfert": recommandation.transfert,
        "resume": recommandation.resume_3_points, "passed": True
    }


if __name__ == "__main__":
    result = simulate_cas2()
    print(f"\nRésultat global : {'PASSÉ' if result['passed'] else 'ÉCHOUÉ'}")
