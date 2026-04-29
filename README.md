# HealthGuard IA

Prototype d'assistance au diagnostic medical pour zones rurales, avec moteur hybride arbre clinique + modele ML, interface PWA et synchronisation vers PostgreSQL.

## Etat actuel

Au 28 avril 2026, l'etat reel du depot est le suivant:

- API FastAPI fonctionnelle;
- base SQLite locale persistante;
- chiffrement local de certains champs sensibles;
- queue de synchronisation SQLite -> PostgreSQL;
- PWA de demonstration avec historique navigateur;
- mecanisme PIN integre via endpoints de hash et verification;
- documentation historique de soutenance encore presente dans `docs/`.

Le depot doit etre lu comme un prototype technique avance, pas comme une application medicale prete production.

## Structure utile

```text
healthguad/
├── src/
│   ├── api/
│   ├── database/
│   ├── decision_engine/
│   ├── ml/
│   └── security/
├── data/
│   ├── clinical/
│   ├── db/
│   ├── epidemio/
│   └── ml/
├── prototype/
├── tests/
└── docs/
```

## Installation locale

```bash
pip install -r requirements.txt
copy .env.example .env
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Puis ouvrir:

```text
http://localhost:8000
```

## Configuration

Le fichier `.env` local pilote:

- l'acces PostgreSQL local;
- le PIN local de derivation de la cle SQLite;
- le sel stable utilise pour relire les donnees chiffrees apres redemarrage.

Un exemple minimal est fourni dans [`.env.example`](./.env.example).

## Flux principal

1. Creation patient via l'API locale
2. Diagnostic via moteur arbre + ML
3. Ecriture SQLite locale
4. Ajout a la queue de synchronisation
5. Synchronisation vers PostgreSQL sur declenchement

## Notes importantes

- `docs/RAPPORT_LIVRABLE.md` est un document de livrable historique, pas une specification d'execution exacte.
- `AUDIT_ECARTS_DOC_CODE.md`, `PLAN_CORRECTION_PRIORISE.md` et `AUDIT_SECURITE.md` decrivent les ecarts et corrections en cours.
- `evolution.md` suit l'avancement des corrections.
