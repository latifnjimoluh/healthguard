# Audit des Ecarts Doc vs Code

Date: 2026-04-28
Projet: HealthGuard IA

## Objet

Ce document synthétise les écarts entre:

- la documentation du projet;
- le code réellement exécuté;
- la configuration et les données présentes dans le dépôt.

Il faut lire l'application comme un prototype intégré avancé, pas comme une solution médicale prête pour la production.

## Résumé exécutif

Le projet est techniquement plus qu'une maquette:

- une API FastAPI est en place;
- un moteur hybride arbre clinique + ML est implémenté;
- une PWA existe;
- un schéma SQLite et un export PostgreSQL existent;
- une base de tests substantielle est présente.

En revanche, plusieurs éléments décrits dans la documentation sont partiellement vrais, simulés, ou non intégrés de bout en bout:

- la persistance locale réelle n'est pas celle annoncée;
- la sécurité opérationnelle est incomplète;
- des secrets et des données nominatives sont versionnés;
- plusieurs briques existent mais ne sont pas branchées au flux principal.

## Constat principal

La documentation présente une architecture cible plus mature que l'architecture réellement exécutée.

La formule la plus juste pour décrire l'état du projet est:

Prototype fonctionnel offline-first avec backend réel, mais persistance locale, sécurité opérationnelle et gouvernance des données encore incomplètes.

## Ecarts détaillés

### 1. Persistance locale

La documentation décrit une base SQLite locale chiffrée et persistante.

Constat code:

- l'API active initialise la base via `get_in_memory_db()` dans `src/api/app.py`;
- la base utilisée au runtime est donc en mémoire;
- le prototype frontend repose largement sur `localStorage`.

Impact:

- les données backend locales ne sont pas durablement persistées comme le laisse entendre la documentation;
- le comportement réel de l'application dépend davantage du navigateur que de SQLite.

### 2. Chiffrement des données

La documentation promet un chiffrement fort des données au repos.

Constat code:

- le module `src/database/encryption.py` implémente bien un chiffrement AES-CBC + HMAC avec dérivation PBKDF2;
- les symptômes et recommandations sont chiffrés dans le flux `/api/v1/diagnostic/new`;
- mais le dump PostgreSQL versionné contient des noms lisibles en clair dans la colonne `nom_chiffre`;
- le flux `sync/from-browser` réinjecte lui-même des noms patients en clair.

Impact:

- la promesse "données patient chiffrées au repos" n'est pas tenue de manière cohérente sur l'ensemble du système;
- le nommage des colonnes donne même une impression de sécurité qui n'est pas confirmée par les données réelles.

### 3. Gestion du PIN et authentification

La documentation insiste sur Argon2id et la sécurité PIN.

Constat code:

- un vrai module existe dans `src/security/pin_auth.py`;
- il gère hachage Argon2id, vérification et verrouillage progressif;
- mais il n'est pas intégré au parcours principal du prototype;
- l'API utilise une clé de dev dérivée du PIN fixe `"123456"`;
- le frontend stocke un pseudo PIN côté navigateur via `localStorage`.

Impact:

- le mécanisme de sécurité existe comme brique technique;
- il n'est pas appliqué bout en bout dans l'expérience réelle.

### 4. Synchronisation

La documentation décrit un modèle de sync offline sécurisé via queue locale chiffrée.

Constat code:

- `src/database/sync.py` et `src/database/postgres_sync.py` implémentent bien une queue locale et une sync PostgreSQL;
- mais le prototype UI utilise surtout `/api/v1/sync/from-browser`;
- ce flux synchronise directement des données issues de `localStorage` vers PostgreSQL;
- cela contourne une partie du modèle SQLite local chiffré décrit dans la doc.

Impact:

- deux modèles de synchronisation coexistent;
- le flux réellement utilisé par l'UI est plus simple mais moins cohérent avec l'architecture documentée.

### 5. Audit trail et sécurité transport

La documentation présente l'audit trail et TLS comme des garanties actives.

Constat code:

- `src/database/audit.py` contient une vraie chaîne de hash;
- `src/security/tls_sync.py` est explicitement un simulateur;
- ces mécanismes sont surtout présents comme briques et tests;
- ils ne structurent pas le flux principal navigateur -> API -> PostgreSQL.

Impact:

- l'audit et la sécurité transport sont partiellement démonstratifs;
- ils ne doivent pas être présentés comme contrôles opérationnels pleinement actifs.

### 6. PWA et offline

La documentation PWA est globalement vraie, mais incomplète sur le niveau réel d'offline.

Constat code:

- `manifest.json` et `sw.js` existent;
- le service worker met bien en cache les écrans et assets statiques;
- les appels API ne sont pas mis en cache;
- le plan mentionnait IndexedDB, mais l'implémentation actuelle repose encore sur `localStorage`.

Impact:

- l'application est installable et partiellement offline;
- le mode offline avancé décrit dans la feuille de route n'est pas totalement atteint.

### 7. Cohérence documentaire

La documentation contient plusieurs incohérences de détail.

Exemples:

- le rapport cite `src/security/auth.py`, alors que le fichier réel est `src/security/pin_auth.py`;
- le rapport mentionne AES-256-GCM, alors que l'implémentation active est AES-CBC + HMAC;
- la doc décrit parfois une architecture cible alors qu'elle la présente comme déjà réalisée.

Impact:

- la documentation mélange état actuel, architecture cible et éléments de soutenance;
- elle doit être relue avant usage technique ou présentation externe.

## Ce qui est réellement solide

Malgré les écarts, plusieurs éléments sont réels et exploitables:

- moteur d'arbres cliniques présent;
- inférence ML présente;
- agrégateur présent;
- API fonctionnelle;
- frontend PWA fonctionnel;
- export PostgreSQL réel;
- base de tests importante.

## Conclusion

Le dépôt contient un démonstrateur sérieux avec un vrai socle logiciel. En revanche, il ne faut pas présenter son état actuel comme une application médicale sécurisée, chiffrée et durablement offline au sens production.

Les écarts les plus importants concernent:

- la sécurité des secrets;
- l'exposition de données nominatives;
- la persistance locale effective;
- l'écart entre architecture décrite et architecture réellement exécutée.
