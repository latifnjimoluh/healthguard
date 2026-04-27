# HealthGuard IA

Application mobile de diagnostic médical assisté par intelligence artificielle pour les zones rurales du Cameroun (districts sanitaires d'Adamaoua et de l'Est).

## Contexte

Les agents de santé communautaires en zones rurales interviennent souvent sans connexion internet fiable, avec du matériel limité, dans des conditions d'urgence. HealthGuard IA leur fournit un assistant de diagnostic clinique fonctionnant **100% hors ligne**, combinant des arbres décisionnels cliniques (PCIME/IMCI OMS) et un modèle de machine learning embarqué.

## Fonctionnalités principales

- **5 arbres décisionnels cliniques** : Paludisme, IRA/Pneumonie, Malnutrition MAS, Diarrhée/Choléra, Tuberculose
- **Moteur hybride arbre + ML** : Arbre (60%) + XGBoost INT8 (40%), avec override ROUGE prioritaire
- **Chiffrement bout en bout** : AES-256-CBC pour les données au repos, Argon2id pour les PINs
- **Audit trail** : Chaîne de hachage SHA-256 pour la traçabilité (registre immuable)
- **Synchronisation opportuniste** : Queue offline avec retry automatique dès reconnexion
- **Prototype HTML** : 7 écrans Mobile First (720×1560px)

## Structure du projet

```
healthguard/
├── src/
│   ├── api/                    # FastAPI — 7 endpoints REST
│   ├── database/               # SQLite + chiffrement + audit + sync
│   ├── decision_engine/        # Arbres JSON + agrégateur + recommandations
│   ├── ml/                     # XGBoost, génération données, inférence
│   └── security/               # PIN Argon2id, AES-256, TLS sync
├── data/
│   ├── db/                     # Schéma SQL + base SQLite
│   ├── trees/                  # 5 arbres décisionnels JSON (format FHIR-like)
│   └── ml/                     # Modèle entraîné (.pkl) + features
├── prototype/
│   ├── css/                    # Design System Material Design 3
│   └── screens/                # 7 écrans HTML (E1–E7)
├── tests/                      # 134 tests unitaires (85% couverture)
└── docs/                       # Documentation technique
```

## Installation

```bash
# Cloner et installer les dépendances
pip install -r requirements.txt

# Lancer l'API locale
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload

# Lancer les tests
pytest tests/ --cov=src -v

# Ré-entraîner le modèle (si nécessaire)
python src/ml/train_model.py
```

## Performances du modèle ML

| Métrique | Valeur | Cible |
|----------|--------|-------|
| Précision globale | 97.0% | — |
| Sensibilité paludisme grave | 97.3% | ≥ 85% ✓ |
| Sensibilité tuberculose | 100.0% | ≥ 80% ✓ |
| Taille modèle | ~7.2 MB | < 8 MB ✓ |
| Couverture tests | 85% | > 80% ✓ |

## Architecture de sécurité (STRIDE)

| Menace | Contre-mesure |
|--------|--------------|
| Spoofing (S) | Argon2id PIN, timeout session 5min |
| Tampering (T) | AES-256-CBC + HMAC-SHA256, audit chain |
| Repudiation (R) | Audit trail SHA-256 immuable |
| Information Disclosure (I) | Chiffrement AES-256 au repos |
| Denial of Service (D) | Verrouillage exponentiel (5s → 625s) |
| Elevation of Privilege (E) | Accès urgence limité, pas de rôle admin mobile |

## Protocoles cliniques implémentés

- **Paludisme** : Critères OMS paludisme grave (convulsions, trouble conscience, hyperthermie ≥ 40°C)
- **IRA/Pneumonie** : Seuils PCIME/IMCI tachypnée par âge (2 mois / 12 mois / 5 ans / adulte)
- **Malnutrition** : PB < 115mm (MAS), 115-125mm (MAM), test appétit RUTF
- **Diarrhée/Choléra** : Plans de réhydratation OMS A/B/C, protocole alerte épidémique
- **Tuberculose** : Critères CDTB — toux > 3 semaines, hémoptysie, contact connu

## PIN démo (prototype)

Code PIN de démonstration : **246810**

> Usage réservé au personnel de santé habilité — Ministère de la Santé du Cameroun
