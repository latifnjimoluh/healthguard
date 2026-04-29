# Audit Securite

Date: 2026-04-28
Projet: HealthGuard IA

## Portée

Cet audit couvre:

- secrets et configuration;
- données sensibles;
- chiffrement;
- PIN et authentification;
- synchronisation;
- stockage navigateur;
- exposition documentaire.

## Niveau de risque global

Risque global actuel: élevé.

La raison principale n'est pas l'absence de briques de sécurité, mais leur intégration incomplète et l'exposition directe de secrets et de données.

## Risques majeurs

### 1. Secrets exposés

Constat:

- `.env` contient des identifiants PostgreSQL réels;
- ce fichier est présent à la racine du projet.

Risque:

- accès non autorisé à la base centrale;
- réutilisation des credentials dans d'autres contextes;
- fuite immédiate en cas de partage du dépôt.

Correction:

- rotation du mot de passe;
- retrait du secret du dépôt;
- introduction de `.env.example`.

### 2. Données nominatives exposées

Constat:

- le dump PostgreSQL contient des noms patients et agents en clair;
- les champs supposés chiffrés ne le sont pas systématiquement en pratique.

Risque:

- fuite de données personnelles;
- non-conformité forte en contexte médical;
- atteinte à la crédibilité du projet.

Correction:

- anonymiser le dump;
- supprimer les données réelles du dépôt;
- clarifier la politique de données de test.

### 3. PIN non sécurisé de bout en bout

Constat:

- un module Argon2 existe;
- mais le frontend stocke une valeur PIN côté `localStorage`;
- le backend dérive une clé à partir d'un PIN fixe de développement.

Risque:

- sécurité contournable;
- faux sentiment de protection;
- impossibilité de prétendre à une authentification robuste.

Correction:

- intégrer réellement `pin_auth.py`;
- cesser de stocker le PIN brut ou pseudo-brut côté navigateur;
- séparer clairement mode démo et mode réel.

### 4. Incohérence du chiffrement

Constat:

- le code chiffre certains payloads localement;
- le flux navigateur vers PostgreSQL envoie des données qui finissent lisibles en base;
- la documentation présente un chiffrement plus homogène qu'en réalité.

Risque:

- rupture du modèle de protection;
- difficulté à garantir quelles données sont réellement protégées.

Correction:

- définir une matrice précise:
  quelles données sont chiffrées, à quel moment, avec quelle clé, jusqu'où;
- aligner code, schéma et documentation.

### 5. Stockage navigateur trop exposé

Constat:

- le prototype stocke des consultations et métadonnées utilisateur dans `localStorage`.

Risque:

- lecture facile depuis le navigateur;
- persistance non sécurisée sur poste partagé;
- effacement ou corruption simples.

Correction:

- réduire les données sensibles stockées en navigateur;
- migrer les données de travail vers un stockage local plus contrôlé;
- chiffrer localement si ce mode doit rester.

## Risques modérés

### 6. Synchronisation duale et ambiguë

Constat:

- coexistence d'une queue locale chiffrée et d'une sync directe browser -> PostgreSQL.

Risque:

- surface d'attaque et de confusion plus large;
- comportements divergents selon le chemin emprunté.

Correction:

- choisir un flux principal unique;
- documenter les autres comme flux de test ou de migration.

### 7. Sécurité transport simulée

Constat:

- `tls_sync.py` est un simulateur, pas une implémentation de transport durcie.

Risque:

- survente involontaire du niveau de sécurité;
- mauvaise base pour un passage production.

Correction:

- documenter explicitement le caractère simulé;
- concevoir un vrai modèle de transport si nécessaire.

### 8. Audit trail peu branché

Constat:

- la chaîne de hash existe;
- elle n'est pas au centre du flux applicatif principal.

Risque:

- preuve d'intégrité non garantie sur les parcours réellement utilisés.

Correction:

- brancher les événements métiers critiques sur `log_action()`.

## Forces existantes

Les points suivants sont positifs:

- module de chiffrement structuré;
- module PIN Argon2 existant;
- audit trail structuré;
- base de tests importante;
- séparation logique correcte des modules.

Le problème actuel est donc surtout un problème d'intégration, de gouvernance et de cohérence d'ensemble.

## Recommandations immédiates

1. Faire tourner les secrets et sortir `.env` des contenus partageables.
2. Retirer ou anonymiser le dump PostgreSQL.
3. Corriger la documentation de sécurité pour qu'elle reflète le code réel.
4. Remplacer le PIN de dev fixe par un mécanisme réel ou l'indiquer clairement comme mode démo.
5. Choisir une stratégie unique de stockage et de synchronisation.

## Recommandations court terme

1. Passer la base locale active sur SQLite fichier.
2. Brancher le module PIN au frontend et au backend.
3. Définir une vraie politique de chiffrement des champs sensibles.
4. Réduire l'usage de `localStorage` pour les données de santé.
5. Ajouter des tests d'intégration sécurité.

## Conclusion

Le projet contient de bonnes intentions et plusieurs briques sérieuses, mais il n'est pas actuellement défendable comme application médicale sécurisée au sens opérationnel.

La priorité n'est pas d'ajouter des fonctionnalités de sécurité supplémentaires. La priorité est d'arrêter les expositions actuelles, puis d'aligner les flux réels sur les mécanismes déjà codés.
