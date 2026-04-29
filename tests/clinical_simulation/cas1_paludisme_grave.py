"""
Simulation Cas 1  Paludisme Grave Pédiatrique
Patient : Garçon, 3 ans, 13kg, Village Tibati, Adamaoua
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.decision_engine.aggregator import aggregate
from src.decision_engine.recommendation import generate_recommendation


def simulate_cas1():
    """Rejoue le Cas 1 et vérifie les assertions cliniques."""
    print("\n" + "="*60)
    print("CAS 1  PALUDISME GRAVE PÉDIATRIQUE")
    print("="*60)
    print("Patient : Garçon, 3 ans, 13 kg, Village Tibati, Adamaoua")
    print("Symptômes : Fièvre 40.1°C, vomissements x5/24h, convulsions, somnolent")
    print("-"*60)

    symptomes = {
        "age_ans": 3,
        "poids_kg": 13,
        "sexe": 1,
        "fievre": 1,
        "temperature_celsius": 40.1,
        "vomissements": 1,
        "convulsions": 1,
        "trouble_conscience": 1,
        "duree_symptomes_jours": 3,
        "saison_pluie": 1,
        "zone_endemie_tb": 0,
        "frissons": 1,
        "cephalee": 1,
        "grossesse": 0
    }

    resultat = aggregate(symptomes)
    recommandation = generate_recommendation(resultat)

    print(f"\nRésultat diagnostic :")
    print(f"  Diagnostic principal : {resultat.diagnostic_principal}")
    print(f"  Probabilité          : {resultat.probabilite_combinee*100:.1f}%")
    print(f"  Score gravité        : {resultat.gravite}/3")
    print(f"  Couleur alerte       : {resultat.couleur_alerte}")
    print(f"  Transfert            : {recommandation.transfert}")

    print(f"\nRecommandation (résumé) :")
    for i, point in enumerate(recommandation.resume_3_points, 1):
        print(f"  {i}. {point}")

    print(f"\nContre-indications : {resultat.contre_indications}")

    # === ASSERTIONS CLINIQUES ===
    passed = True

    # Assertion 1 : Paludisme grave
    assert "paludisme_grave" in resultat.diagnostic_principal, \
        f"FAIL: diagnostic={resultat.diagnostic_principal}, attendu paludisme_grave"
    print("\n✓ Diagnostic paludisme_grave confirmé")

    # Assertion 2 : Gravité maximale
    assert resultat.gravite == 3, f"FAIL: gravite={resultat.gravite}, attendu 3"
    print("✓ Gravité 3/3 confirmée")

    # Assertion 3 : Couleur ROUGE
    assert resultat.couleur_alerte == "ROUGE", f"FAIL: couleur={resultat.couleur_alerte}"
    print("✓ Alerte ROUGE confirmée")

    # Assertion 4 : Transfert requis
    assert recommandation.transfert["requis"] is True, "FAIL: transfert non requis"
    print("✓ Transfert requis confirmé")

    # Assertion 5 : Contre-indication AL oral (CRITIQUE)
    cl = str(resultat.contre_indications)
    assert "artemether_lumefantrine_oral" in cl, \
        f"FAIL: contre-indication AL oral manquante dans {cl}"
    print("✓ Contre-indication AL oral présente (CRITIQUE)")

    # Assertion 6 : Résumé contient action urgente
    resume_str = " ".join(recommandation.resume_3_points).upper()
    assert any(mot in resume_str for mot in ["TRANSFERT", "URGENCE", "ROUGE"]), \
        "FAIL: action urgente absente du résumé"
    print("✓ Action urgente dans le résumé")

    print(f"\n{'='*60}")
    print("CAS 1 : TOUTES LES ASSERTIONS PASSÉES ✓")
    print(f"{'='*60}")

    return {
        "cas": 1,
        "description": "Paludisme grave pédiatrique",
        "diagnostic": resultat.diagnostic_principal,
        "gravite": resultat.gravite,
        "couleur": resultat.couleur_alerte,
        "transfert": recommandation.transfert,
        "resume": recommandation.resume_3_points,
        "passed": True
    }


if __name__ == "__main__":
    result = simulate_cas1()
    print(f"\nRésultat global : {'PASSÉ' if result['passed'] else 'ÉCHOUÉ'}")
