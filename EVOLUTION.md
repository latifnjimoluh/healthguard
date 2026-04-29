# Evolution des Corrections

Date de démarrage: 2026-04-28
Projet: HealthGuard IA

## Objectif

Suivre l'avancement des corrections structurelles demandées après audit:

- alignement doc / code;
- persistance locale réelle;
- unification de la synchronisation;
- intégration réelle du PIN;
- réduction des écarts de sécurité;
- ajout de `.env.example`.

## Etat global

Progression: 7 / 7
Statut: CORRECTION STRUCTURELLE TERMINEE

Progression complementaire interface: 2 / 2
Statut interface: LOGO INTEGRE ET FLUX FRONTEND HARMONISE

## Phases

### Phase 1. Cadre de correction

- [x] Créer `evolution.md`
- [x] Ajouter `.env.example`
- [x] Définir l'architecture cible de correction dans le code

### Phase 2. Persistance locale réelle

- [x] Remplacer la base active en mémoire par une SQLite fichier persistante
- [x] Stabiliser la clé de chiffrement locale pour éviter la perte de lecture après redémarrage

### Phase 3. Synchronisation unifiée

- [x] Brancher les créations patient / diagnostic sur la queue locale
- [x] Faire de `sync/trigger` le flux principal
- [x] Réduire le rôle de `sync/from-browser` à l'import de secours

### Phase 4. Intégration PIN

- [x] Exposer des endpoints de hash / vérification PIN
- [x] Migrer le frontend pour ne plus stocker les PIN en clair
- [x] Brancher le changement de PIN à ce flux

### Phase 5. Frontend métier

- [x] Corriger le flux E3 -> E5 pour créer un patient réel avant diagnostic
- [x] Corriger la sauvegarde locale et la sync côté interface

### Phase 6. Tests

- [x] Adapter / compléter les tests API
- [x] Exécuter la suite de tests

### Phase 7. Documentation

- [x] Mettre à jour les documents principaux pour refléter l'état réel corrigé

### Phase 8. Corrections de l'Audit (Post-Audit 2026-04-28)

- [x] Chiffrement complet des données patients (date_naissance, sexe, village_code)
- [x] Activation réelle de l'Audit Trail sur les endpoints critiques
- [x] Persistance des traitements comme entités métier
- [x] Sécurisation du PIN local et suppression des valeurs par défaut triviales
- [x] Amélioration de la synchronisation (TLS 1.3 forcé et audit)

### Phase 9. Unification et Modèle IA (Post-Audit 2026-04-28)

- [x] Unification du parcours de diagnostic (API locale prioritaire sur JS)
- [x] Suppression des PIN de démonstration de l'interface utilisateur
- [x] Désactivation de l'entraînement automatique en production
- [x] Correction de l'imputation SpO2 (NaN au lieu de 97%)
- [x] Anonymisation des dumps SQL de référence (full_export.sql)

### Phase 10. Gestion des Comptes et PIN (Post-Audit 2026-04-28)

- [x] Création de la table `agents` locale dans SQLite
- [x] Persistance des hachages PIN (Argon2id) en base de données locale
- [x] Implémentation de l'endpoint de modification du PIN (`/api/v1/security/pin/change`)
- [x] Interface de changement de PIN dans les paramètres (modal multi-étapes)
- [x] Unification de la création d'agent (hachage côté serveur systématique)

### Phase 11. Authentification Biométrique (Post-Audit 2026-04-28)

- [x] Extension du schéma SQLite pour le stockage des clés publiques biométriques
- [x] Création des endpoints WebAuthn (options/verify) dans l'API
- [x] Interface d'activation biométrique dans `e7_settings.html`
- [x] Intégration du bouton BIO sur l'écran de connexion `e1_login.html`
- [x] Simulation du flux de scan pour environnement local/prototype

## Journal

- 2026-04-28: début de l'application des corrections suite à l'audit approfondi.
- 2026-04-28: planification de la Phase 8 (Sécurité & Audit Trail).
- 2026-04-28: mise en oeuvre du chiffrement complet des données identifiantes patients et activation de la chaîne de hashage de l'audit trail.
- 2026-04-28: ajout de la persistance granulaire des traitements dans SQLite.
- 2026-04-28: forçage de TLS 1.3 dans la configuration Nginx et retrait des PIN par défaut triviaux.
- 2026-04-28: unification du diagnostic frontend : l'API locale est désormais le chemin unique, le JS n'est qu'un secours.
- 2026-04-28: anonymisation des données sensibles dans les dumps SQL et masquage des PIN de démonstration.
- 2026-04-28: sécurisation du modèle IA (déterminisme et correction de l'imputation SpO2).
- 2026-04-28: migration de la gestion des agents vers SQLite locale avec hachage Argon2id persistant et interface de changement de PIN.
- 2026-04-28: implémentation complète de l'authentification biométrique (WebAuthn style) pour un accès ultra-rapide des agents de santé.

