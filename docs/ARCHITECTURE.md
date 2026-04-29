# Architecture Technique - Etat Courant

Date de mise a jour: 2026-04-28

## Positionnement

Ce document decrit l'architecture d'execution actuelle du depot, et non l'architecture cible historique de soutenance.

## Vue d'ensemble

```text
PWA HTML/CSS/JS
    |
    v
FastAPI locale
    |
    +--> Moteur arbre + ML
    |
    +--> SQLite locale persistante
    |      |
    |      +--> patients
    |      +--> consultations
    |      +--> diagnostics
    |      +--> sync_queue
    |
    +--> Synchronisation manuelle / differée
           |
           v
       PostgreSQL local ou district
```

## Composants reels

### Frontend

- interface dans `prototype/screens/`;
- manifest PWA et service worker;
- stockage navigateur conserve pour l'historique de presentation et l'import de secours.

### Backend

- API dans `src/api/app.py`;
- creation patient, diagnostic, sync et verification PIN;
- la base active n'est plus en memoire mais en SQLite fichier.

### Base locale

- schema SQL dans `data/db/schema.sql`;
- initialisation via `src/database/schema.py`;
- chiffrement de champs via `src/database/encryption.py`.

### Synchronisation

Flux principal courant:

1. patient cree localement;
2. consultation + diagnostic ecrits en SQLite;
3. payload ajoute a `sync_queue`;
4. `sync/trigger` pousse les elements vers PostgreSQL.

`sync/from-browser` reste un flux de secours d'import des consultations navigateur vers SQLite locale.

### Securite

- PIN hache via `src/security/pin_auth.py`;
- verification PIN exposee par l'API;
- cle de chiffrement locale derivee d'un PIN local stable et d'un sel stable configure.

## Limites actuelles

- le stockage navigateur existe encore pour l'historique UI;
- la documentation historique de livrables est plus large que l'etat d'execution reel;
- le transport reseau durci reste a renforcer pour un contexte production.

## Documents lies

- `README.md`
- `AUDIT_ECARTS_DOC_CODE.md`
- `PLAN_CORRECTION_PRIORISE.md`
- `AUDIT_SECURITE.md`
- `evolution.md`
