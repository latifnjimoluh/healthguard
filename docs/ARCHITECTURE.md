# Architecture Technique — HealthGuard IA

## Vue d'ensemble

HealthGuard IA est une application **offline-first** conçue pour Android, avec une API REST locale (FastAPI) exposée en localhost. Toute la logique de diagnostic est embarquée sur l'appareil — aucune dépendance réseau pour le diagnostic.

```
┌─────────────────────────────────────────────────────────┐
│                    Couche Présentation                   │
│   HTML/CSS/JS (prototype) ──► Android WebView (prod)    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP localhost:8000
┌──────────────────────▼──────────────────────────────────┐
│                    API REST (FastAPI)                    │
│  /diagnostic/new  /patients/*  /sync/*  /health         │
└──────────────────────┬──────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
┌────────▼────────┐       ┌─────────▼──────────┐
│  Moteur de       │       │  Base de Données   │
│  Décision        │       │  SQLite (chiffrée) │
│                  │       │                    │
│  Arbres JSON     │       │  patients          │
│  (5 maladies)    │       │  consultations     │
│     +            │       │  diagnostics       │
│  XGBoost ML      │       │  audit_log         │
│  (INT8)          │       │  sync_queue        │
└─────────────────┘       └────────────────────┘
```

## Moteur de décision hybride

### Flux de décision

```
Symptômes
    │
    ├─► Arbres décisionnels (5 × JSON FHIR-like)
    │       └─► ResultatDiagnostic (gravite 0-3, couleur, traitement)
    │
    ├─► Modèle XGBoost (INT8 quantifié)
    │       └─► ProbabilitesDiagnostic (top1, top2, proba)
    │
    └─► Agrégateur (aggregator.py)
            │
            ├─ ROUGE override (gravité=3) → 100% arbre
            ├─ Concordance forte + gravité ≥ 2 → 80% arbre / 20% ML
            └─ Défaut → 60% arbre / 40% ML
```

### Arbres décisionnels

Format JSON avec 4 types de noeuds :
- `question` (booléen) : présence/absence d'un symptôme
- `mesure` (numérique) : valeur quantitative (température, PB, SpO2)
- `classification` (routing) : branchement selon âge/groupe
- `resultat` (feuille) : diagnostic + gravité + traitement

Chaque résultat contient :
```json
{
  "diagnostic": "paludisme_grave",
  "gravite": 3,
  "couleur_alerte": "ROUGE",
  "action_immediate": "TRANSFERT_URGENCE",
  "traitement": ["artemether_im"],
  "contre_indications": ["artemisinine_orale"],
  "notification_district": false
}
```

## Sécurité

### Chiffrement des données au repos

```
PIN (6 chiffres)
    │
    ▼ Argon2id (time=3, mem=64MB, par=4)
Hash PIN
    │
    ▼ (séparé)
PIN + sel aléatoire
    │
    ▼ PBKDF2-SHA256 (256 000 itérations)
Clé AES-256 (32 bytes)
    │
    ▼ Encrypt-then-MAC
Ciphertext (AES-256-CBC) + HMAC-SHA256
```

### Audit trail (chaîne de hachage)

```
Log[0]: SHA256("0"*64 + action + timestamp) = hash_0
Log[1]: SHA256(hash_0 + action + timestamp) = hash_1
Log[n]: SHA256(hash_n-1 + action + timestamp) = hash_n
```
Toute modification d'un log rompt la chaîne — détectable par `verify_chain_integrity()`.

## Synchronisation offline

```
Consultation créée localement
    │
    ▼
sync_queue (SQLite)
  - payload chiffré (AES-256)
  - tentatives: 0
  - statut: PENDING
    │
    ▼ (dès reconnexion)
Sync service
  - Retry exponentiel (max 3 tentatives)
  - TLS 1.3 + mTLS pour le transport
  - Format FHIR-compatible
    │
    ▼
Serveur district
```

## Structure des tables SQLite

```sql
patients         (id_patient, nom_chiffre, date_naissance, sexe, village_code)
consultations    (id_consultation, id_patient, date_heure, agent_id, symptomes_json, statut_sync)
diagnostics      (id_diagnostic, id_consultation, maladie_code, probabilite_ml, recommandation_json, gravite_score)
traitements      (id_traitement, id_diagnostic, medicament_code, posologie, voie_admin)
audit_log        (id_log, timestamp, user_id, action_type, table_cible, hash_precedent, hash_actuel)
sync_queue       (id_queue, table_cible, operation, payload_chiffre, tentatives, derniere_tentative)
ref_maladies     (code_maladie, nom_fr, nom_local, arbre_json_path, actif)
```

## Performance et contraintes matérielles

| Contrainte | Valeur cible | Valeur atteinte |
|------------|-------------|-----------------|
| Inférence ML | < 300ms | ~15ms (XGBoost) |
| Taille modèle | < 8 MB | ~7.2 MB |
| RAM utilisée | < 200 MB | ~80 MB |
| Stockage app | < 50 MB | ~35 MB |
| Android min | API 21 (Android 5.0) | — |
