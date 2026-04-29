# Plan de Correction Priorise

Date: 2026-04-28
Projet: HealthGuard IA

## Objectif

Réduire rapidement l'écart entre la documentation, le code et le niveau réel de sécurité du projet, en commençant par les risques concrets.

## Priorité 0

### 1. Retirer les secrets du dépôt

Actions:

- supprimer le mot de passe réel de `.env`;
- créer un `.env.example` sans secret;
- faire tourner un nouveau mot de passe PostgreSQL;
- vérifier qu'aucun autre secret n'est versionné.

Résultat attendu:

- le dépôt redevient partageable sans exposer l'infrastructure.

### 2. Retirer ou anonymiser les données nominatives

Actions:

- retirer `data/db/healthguard_full_export.sql` de la diffusion publique, ou le remplacer par un export anonymisé;
- pseudonymiser noms patients, noms agents et textes libres;
- documenter la nature démonstrative du dataset.

Résultat attendu:

- plus de données nominatives directement exposées dans le repo.

### 3. Corriger immédiatement la documentation

Actions:

- distinguer clairement "état actuel" et "architecture cible";
- corriger les références de fichiers faux ou obsolètes;
- corriger les mentions crypto incompatibles avec le code réel.

Résultat attendu:

- un lecteur comprend ce qui est réellement implémenté.

## Priorité 1

### 4. Passer de SQLite mémoire à SQLite fichier

Actions:

- remplacer `get_in_memory_db()` par `initialize_database()` sur un fichier local;
- définir un chemin de base locale stable;
- vérifier les migrations et le comportement au redémarrage.

Résultat attendu:

- la persistance locale réelle correspond enfin au design annoncé.

### 5. Unifier le flux de synchronisation

Actions:

- choisir un flux principal unique:
  soit browser `localStorage` -> API -> PostgreSQL;
  soit SQLite local -> queue -> PostgreSQL;
- brancher l'UI sur ce flux unique;
- éviter les doubles logiques concurrentes.

Résultat attendu:

- l'architecture devient lisible, maintenable et testable.

### 6. Intégrer réellement le module PIN

Actions:

- utiliser `src/security/pin_auth.py` pour stocker et vérifier les PIN;
- arrêter le stockage naïf du PIN dans `localStorage`;
- faire correspondre PIN, dérivation de clé et session réelle.

Résultat attendu:

- le mécanisme de sécurité documenté devient actif.

## Priorité 2

### 7. Sécuriser la chaîne de données côté PostgreSQL

Actions:

- décider ce qui doit être chiffré avant arrivée en base centrale;
- harmoniser la signification de `nom_chiffre`;
- éviter l'insertion en clair par `sync/from-browser`;
- revoir le modèle de colonnes si nécessaire.

Résultat attendu:

- les données centrales respectent une politique cohérente.

### 8. Brancher l'audit trail dans les flux métiers

Actions:

- journaliser création patient, diagnostic, sync et accès critique;
- exposer la vérification d'intégrité en administration;
- couvrir ces flux par tests.

Résultat attendu:

- l'audit trail devient un mécanisme réel et non seulement une brique isolée.

### 9. Clarifier la sécurité transport

Actions:

- marquer `tls_sync.py` comme simulateur de façon explicite dans la doc;
- si une vraie sync réseau est visée, définir la stratégie réelle: TLS, certificats, auth machine, rotation secrets.

Résultat attendu:

- pas d'ambiguïté entre simulation et production.

## Priorité 3

### 10. Monter le niveau offline

Actions:

- remplacer progressivement `localStorage` par IndexedDB pour les consultations;
- définir une stratégie de file locale robuste;
- gérer reprise, conflit et rejeu.

Résultat attendu:

- le mode offline devient crédible sur volume et durée.

### 11. Renforcer les tests d'intégration

Actions:

- tests de persistance redémarrage;
- tests de sync réelle avec base PostgreSQL de test;
- tests UI -> API -> base;
- tests de sécurité PIN et chiffrement dans les parcours utilisateur.

Résultat attendu:

- les écarts résiduels sont détectés plus tôt.

## Ordre recommandé d'exécution

1. Secrets
2. Données nominatives
3. Correction doc
4. SQLite persistante
5. Unification sync
6. Intégration PIN
7. Sécurisation PostgreSQL
8. Audit trail branché
9. Clarification transport
10. Offline robuste
11. Tests d'intégration

## Livrables recommandés

- `SECURITY_HARDENING.md`
- `ARCHITECTURE_ACTUELLE.md`
- `ARCHITECTURE_CIBLE.md`
- `DATA_POLICY.md`
- `SYNC_FLOW.md`

## Conclusion

Le plus urgent n'est pas d'ajouter de nouvelles fonctionnalités. Le plus urgent est de fermer les expositions actuelles et d'aligner le dépôt avec ce qu'il prétend faire.
