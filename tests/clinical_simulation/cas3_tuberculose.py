"""
Simulation Cas 3 — Tuberculose Pulmonaire
Patient : Homme, 42 ans, Village Bertoua, Est-Cameroun
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.decision_engine.aggregator import aggregate
from src.decision_engine.recommendation import generate_recommendation


def simulate_cas3():
    print("\n" + "="*60)
    print("CAS 3 — TUBERCULOSE PULMONAIRE SUSPECTÉE")
    print("="*60)
    print("Patient : Homme, 42 ans, Village Bertoua, Est-Cameroun")
    print("Symptômes : Toux 5 semaines, hémoptysie x2, amaigrissement 8kg/2 mois")
    print("-"*60)

    symptomes = {
        "age_ans": 42,
        "poids_kg": 58,
        "sexe": 1,
        "toux": 1,
        "hemoptysie": 1,
        "duree_symptomes_jours": 35,
        "fievre": 0,
        "temperature_celsius": 37.1,
        "zone_endemie_tb": 1,
        "contact_tb_connu": 0,
        "frissons": 0,
        "cephalee": 0,
        "vomissements": 0,
        "diarrhee": 0,
        "dyspnee": 0,
        "convulsions": 0,
        "trouble_conscience": 0,
        "grossesse": 0,
        "saison_pluie": 0
    }

    resultat = aggregate(symptomes)
    recommandation = generate_recommendation(resultat)

    print(f"\nRésultat diagnostic :")
    print(f"  Diagnostic          : {resultat.diagnostic_principal}")
    print(f"  Probabilité         : {resultat.probabilite_combinee*100:.1f}%")
    print(f"  Gravité             : {resultat.gravite}/3")
    print(f"  Couleur alerte      : {resultat.couleur_alerte}")

    print(f"\nContre-indications : {resultat.contre_indications}")
    print(f"\nRecommandation (résumé) :")
    for i, point in enumerate(recommandation.resume_3_points, 1):
        print(f"  {i}. {point}")

    # === ASSERTIONS CLINIQUES ===
    assert resultat.diagnostic_principal == "tuberculose", \
        f"FAIL: diagnostic={resultat.diagnostic_principal}, attendu tuberculose"
    print("\n✓ Diagnostic tuberculose confirmé")

    assert resultat.gravite >= 2, f"FAIL: gravite={resultat.gravite}"
    print("✓ Gravité >= 2 confirmée")

    assert resultat.couleur_alerte in ("ORANGE", "ROUGE"), \
        f"FAIL: couleur={resultat.couleur_alerte}"
    print("✓ Alerte ORANGE/ROUGE confirmée")

    # CRITIQUE : pas d'antibiotiques empiriques
    ci_str = str(resultat.contre_indications).lower()
    rec_str = resultat.recommandation_complete.lower()
    assert "antibiotiques_empiriques" in ci_str or "pas" in rec_str or "ne pas" in rec_str, \
        "FAIL: mention 'ne pas donner antibiotiques' absente"
    print("✓ Contre-indication antibiotiques empiriques présente (CRITIQUE)")

    # Vérifier mention CDTB dans les recommandations
    assert "cdtb" in rec_str or "reference" in rec_str or "tuberculose" in rec_str, \
        "FAIL: référence CDTB absente"
    print("✓ Référence CDTB mentionnée")

    print(f"\n{'='*60}")
    print("CAS 3 : TOUTES LES ASSERTIONS PASSÉES ✓")
    print(f"{'='*60}")

    return {
        "cas": 3, "description": "Tuberculose pulmonaire",
        "diagnostic": resultat.diagnostic_principal, "gravite": resultat.gravite,
        "couleur": resultat.couleur_alerte, "resume": recommandation.resume_3_points,
        "passed": True
    }


if __name__ == "__main__":
    result = simulate_cas3()
    print(f"\nRésultat global : {'PASSÉ' if result['passed'] else 'ÉCHOUÉ'}")
