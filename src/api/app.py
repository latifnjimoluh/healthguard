"""
Application FastAPI principale pour HealthGuard IA.
API REST locale pour le moteur de diagnostic et la gestion des patients.
"""

import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.database.schema import get_in_memory_db, initialize_database
from src.database.encryption import generate_salt, generate_key, encrypt_field, decrypt_field
from src.decision_engine.aggregator import aggregate
from src.decision_engine.recommendation import generate_recommendation
from src.decision_engine.severity_scorer import calculate_severity_score

# ---- Configuration de l'application ----
app = FastAPI(
    title="HealthGuard IA API",
    description="API de diagnostic médical offline pour zones rurales — Cameroun",
    version="1.0.0"
)

# CORS pour le prototype web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production : limiter aux origines autorisées
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de données en mémoire (pour développement/tests)
_db = None
_encryption_key = None


def get_db():
    """Fournit la connexion à la base de données."""
    global _db
    if _db is None:
        _db = get_in_memory_db()
    return _db


def get_key():
    """Fournit la clé de chiffrement (simulée pour tests)."""
    global _encryption_key
    if _encryption_key is None:
        salt = generate_salt()
        _encryption_key = generate_key("123456", salt)  # PIN de dev
    return _encryption_key


# ---- Modèles Pydantic ----

class SymptomesInput(BaseModel):
    patient_id: str
    agent_id: str
    symptomes: dict


class TreeStepInput(BaseModel):
    session_id: str
    noeud_id: str
    reponse: object


class NouveauPatient(BaseModel):
    nom: str
    date_naissance: Optional[str] = None
    sexe: str
    village_code: str


class ConsultationBrowser(BaseModel):
    """Consultation issue du localStorage du navigateur — données enrichies."""
    date: Optional[str] = None
    patient_nom: Optional[str] = None
    agent_id: Optional[str] = None
    # Patient
    age_ans: Optional[float] = None
    sexe: Optional[str] = None
    village_code: Optional[str] = None
    poids_kg: Optional[float] = None
    # Diagnostic
    diagnostic: Optional[str] = None
    code: Optional[str] = None
    gravite: Optional[int] = None
    couleur: Optional[str] = None
    proba: Optional[float] = None
    decision_arbre: Optional[str] = None
    recommandation: Optional[dict] = None
    # Symptômes
    symptomes: Optional[dict] = None
    synced: Optional[bool] = False


class SyncFromBrowserInput(BaseModel):
    """Données envoyées depuis le localStorage du navigateur."""
    consultations: List[ConsultationBrowser] = []
    agent_id: Optional[str] = None


# ---- Utilitaires ----

def _age_to_birthdate(age_ans: Optional[float]) -> Optional[str]:
    """Convertit un âge en années en date de naissance approximative."""
    if age_ans is None:
        return None
    from datetime import date
    year = date.today().year - int(age_ans)
    return f"{year}-01-01"


# ---- Endpoints ----

@app.get("/api/v1/health")
async def health_check():
    """Vérifie l'état de l'API et du modèle IA."""
    db = get_db()
    try:
        db.execute("SELECT COUNT(*) FROM ref_maladies").fetchone()
        db_status = "ok"
    except Exception:
        db_status = "erreur"

    model_loaded = False
    try:
        from src.ml.inference import _model_cache
        model_loaded = _model_cache is not None
    except Exception:
        pass

    return {
        "status": "ok",
        "version": "1.0.0",
        "model_loaded": model_loaded,
        "db_status": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/v1/diagnostic/new")
async def new_diagnostic(data: SymptomesInput):
    """
    Crée un nouveau diagnostic à partir des symptômes fournis.

    Exécute l'arbre décisionnel + ML et retourne le diagnostic agrégé.
    """
    db = get_db()
    key = get_key()

    # Vérification patient
    patient = db.execute(
        "SELECT id_patient FROM patients WHERE id_patient = ?", (data.patient_id,)
    ).fetchone()

    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {data.patient_id} non trouvé")

    # Calcul du score de gravité
    severity = calculate_severity_score(data.symptomes)

    # Exécution du moteur de décision (arbre + ML)
    try:
        resultat = aggregate(data.symptomes)
        recommandation = generate_recommendation(resultat)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur moteur diagnostic : {str(e)}")

    # Création de la consultation en BDD
    consultation_id = str(uuid.uuid4())
    diagnostic_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    symptomes_chiffre = encrypt_field(json.dumps(data.symptomes), key)

    db.execute(
        """INSERT INTO consultations
           (id_consultation, id_patient, date_heure, agent_id, symptomes_json, statut_sync, created_at)
           VALUES (?, ?, ?, ?, ?, 'PENDING', ?)""",
        (consultation_id, data.patient_id, timestamp, data.agent_id, symptomes_chiffre, timestamp)
    )

    recommandation_json = {
        "resume_3_points": recommandation.resume_3_points,
        "detail_complet": recommandation.detail_complet,
        "medicaments": recommandation.medicaments,
        "transfert": recommandation.transfert,
        "notification_district": recommandation.notification_district
    }

    recommandation_chiffre = encrypt_field(json.dumps(recommandation_json, ensure_ascii=False), key)

    db.execute(
        """INSERT INTO diagnostics
           (id_diagnostic, id_consultation, maladie_code, probabilite_ml,
            decision_arbre, recommandation_json, gravite_score, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            diagnostic_id, consultation_id,
            resultat.diagnostic_principal,
            float(resultat.probabilite_combinee),
            resultat.source_decision,
            recommandation_chiffre,
            resultat.gravite,
            timestamp
        )
    )
    db.commit()

    return {
        "diagnostic_id": diagnostic_id,
        "consultation_id": consultation_id,
        "resultat": {
            "diagnostic": resultat.diagnostic_principal,
            "probabilite": round(resultat.probabilite_combinee * 100, 1),
            "gravite": resultat.gravite,
            "couleur_alerte": resultat.couleur_alerte,
            "diagnostic_differentiel": resultat.diagnostic_differentiel,
            "proba_differentiel": round(resultat.proba_differentiel * 100, 1) if resultat.diagnostic_differentiel else None
        },
        "recommandation": {
            "couleur_alerte": recommandation.couleur_alerte,
            "action_immediate": recommandation.action_immediate,
            "resume_3_points": recommandation.resume_3_points,
            "detail_complet": recommandation.detail_complet,
            "medicaments": recommandation.medicaments,
            "contre_indications": recommandation.contre_indications,
            "transfert": recommandation.transfert,
            "notification_district": recommandation.notification_district,
            "suivi_recommande": recommandation.suivi_recommande
        },
        "severity_score": severity
    }


@app.post("/api/v1/diagnostic/tree-step")
async def tree_step(data: TreeStepInput):
    """
    Avance d'une étape dans l'arbre décisionnel interactif.
    Retourne le prochain noeud ou le résultat final.
    """
    from src.decision_engine.tree_navigator import load_tree, get_next_question

    # Session simplifiée (en production : stocker en Redis ou BDD)
    return {
        "session_id": data.session_id,
        "noeud_id": data.noeud_id,
        "reponse_enregistree": data.reponse,
        "message": "Étape enregistrée — appeler /diagnostic/new avec tous les symptômes"
    }


@app.post("/api/v1/patients/new")
async def create_patient(data: NouveauPatient):
    """Crée un nouveau patient avec données chiffrées."""
    db = get_db()
    key = get_key()

    patient_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # Chiffrement du nom
    nom_chiffre = encrypt_field(data.nom, key)

    db.execute(
        """INSERT INTO patients
           (id_patient, nom_chiffre, date_naissance, sexe, village_code, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, nom_chiffre, data.date_naissance, data.sexe, data.village_code, timestamp, timestamp)
    )
    db.commit()

    return {"patient_id": patient_id, "message": "Patient créé avec succès"}


@app.get("/api/v1/patients/{patient_id}")
async def get_patient(patient_id: str):
    """Récupère le dossier patient avec historique des consultations."""
    db = get_db()
    key = get_key()

    patient = db.execute(
        "SELECT * FROM patients WHERE id_patient = ?", (patient_id,)
    ).fetchone()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient non trouvé")

    # Déchiffrement du nom
    try:
        nom = decrypt_field(patient["nom_chiffre"], key)
    except Exception:
        nom = "[Chiffré]"

    # Récupération des consultations
    consultations = db.execute(
        """SELECT c.id_consultation, c.date_heure, c.agent_id, c.statut_sync,
                  d.maladie_code, d.gravite_score, d.probabilite_ml
           FROM consultations c
           LEFT JOIN diagnostics d ON c.id_consultation = d.id_consultation
           WHERE c.id_patient = ?
           ORDER BY c.date_heure DESC""",
        (patient_id,)
    ).fetchall()

    return {
        "patient": {
            "id": patient_id,
            "nom": nom,
            "sexe": patient["sexe"],
            "village_code": patient["village_code"],
            "created_at": patient["created_at"]
        },
        "consultations": [dict(c) for c in consultations]
    }


@app.get("/api/v1/sync/status")
async def sync_status():
    """Retourne le statut de la queue de synchronisation."""
    from src.database.postgres_sync import test_pg_connection
    db = get_db()

    pending = db.execute(
        "SELECT COUNT(*) as cnt FROM sync_queue WHERE tentatives < 3"
    ).fetchone()["cnt"]

    last_sync = db.execute(
        "SELECT MAX(derniere_tentative) as last FROM sync_queue"
    ).fetchone()["last"]

    pg_ok = test_pg_connection()

    return {
        "pending_sync_count": pending,
        "last_sync": last_sync,
        "connexion_status": "online" if pg_ok else "offline",
        "postgres_disponible": pg_ok
    }


@app.post("/api/v1/sync/from-browser")
async def sync_from_browser(data: SyncFromBrowserInput):
    """
    Reçoit les consultations du localStorage du navigateur
    et les insère directement dans PostgreSQL.
    """
    from src.database.postgres_sync import get_pg_connection, test_pg_connection

    if not test_pg_connection():
        raise HTTPException(status_code=503, detail="PostgreSQL non accessible")

    if not data.consultations:
        return {"success": True, "synced": 0, "message": "Aucune donnée à synchroniser"}

    pg = get_pg_connection()
    cur = pg.cursor()
    synced = 0
    errors = []

    # Récupérer l'établissement principal pour rattacher les patients
    cur.execute("SELECT id_etablissement FROM etablissements WHERE code = 'CMA_NGAOUNDERE_01' LIMIT 1")
    row = cur.fetchone()
    default_etab_id = row[0] if row else None

    for c in data.consultations:
        try:
            agent = c.agent_id or data.agent_id or "prototype"
            ts = c.date or datetime.now(timezone.utc).isoformat()

            # IDs stables basés sur nom + date
            patient_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, c.patient_nom or "anonyme"))
            consult_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c.patient_nom or 'anon'}-{c.date or ''}"))

            # Upsert patient avec toutes les données
            cur.execute(
                """INSERT INTO patients
                   (id_patient, nom_chiffre, date_naissance, sexe, village_code,
                    id_etablissement, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                   ON CONFLICT (id_patient) DO UPDATE SET
                       sexe         = COALESCE(EXCLUDED.sexe, patients.sexe),
                       village_code = COALESCE(EXCLUDED.village_code, patients.village_code),
                       updated_at   = NOW()""",
                (
                    patient_id,
                    c.patient_nom or "Anonyme",
                    _age_to_birthdate(c.age_ans),
                    c.sexe,
                    c.village_code,
                    default_etab_id
                )
            )

            # Upsert consultation avec symptômes JSON
            symptomes_json = json.dumps(c.symptomes, ensure_ascii=False) if c.symptomes else None
            cur.execute(
                """INSERT INTO consultations
                   (id_consultation, id_patient, date_heure, agent_id,
                    symptomes_json, statut_sync, created_at)
                   VALUES (%s, %s, %s, %s, %s, 'SYNCED', NOW())
                   ON CONFLICT (id_consultation) DO UPDATE SET
                       symptomes_json = COALESCE(EXCLUDED.symptomes_json, consultations.symptomes_json),
                       agent_id       = COALESCE(EXCLUDED.agent_id, consultations.agent_id)""",
                (consult_id, patient_id, ts, agent, symptomes_json)
            )

            # Upsert diagnostic avec recommandation et decision_arbre
            diag_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, consult_id + "-diag"))
            recommandation_json = json.dumps(c.recommandation, ensure_ascii=False) if c.recommandation else None
            cur.execute(
                """INSERT INTO diagnostics
                   (id_diagnostic, id_consultation, maladie_code, gravite_score,
                    couleur_alerte, probabilite_ml, decision_arbre,
                    recommandation_json, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                   ON CONFLICT (id_diagnostic) DO UPDATE SET
                       decision_arbre      = COALESCE(EXCLUDED.decision_arbre, diagnostics.decision_arbre),
                       recommandation_json = COALESCE(EXCLUDED.recommandation_json, diagnostics.recommandation_json),
                       gravite_score       = COALESCE(EXCLUDED.gravite_score, diagnostics.gravite_score),
                       couleur_alerte      = COALESCE(EXCLUDED.couleur_alerte, diagnostics.couleur_alerte)""",
                (
                    diag_id, consult_id,
                    c.code or c.diagnostic or "inconnu",
                    c.gravite,
                    c.couleur,
                    round((c.proba or 0) / 100, 4) if c.proba else None,
                    c.decision_arbre,
                    recommandation_json
                )
            )
            synced += 1

        except Exception as e:
            errors.append(f"{c.patient_nom}: {str(e)}")

    pg.commit()

    # Log de sync
    cur.execute(
        """INSERT INTO sync_log (agent_id, nb_consultations, statut, message)
           VALUES (%s, %s, %s, %s)""",
        (data.agent_id or "prototype", synced,
         "SUCCESS" if not errors else "PARTIAL",
         "; ".join(errors) if errors else "OK")
    )
    pg.commit()
    cur.close()
    pg.close()

    return {
        "success": True,
        "synced": synced,
        "errors": errors,
        "message": f"{synced} consultation(s) synchronisée(s) dans PostgreSQL"
    }


@app.get("/api/v1/consultations/recent")
async def get_recent_consultations():
    """Retourne les 10 dernières consultations depuis PostgreSQL."""
    from src.database.postgres_sync import get_pg_connection, test_pg_connection

    if not test_pg_connection():
        raise HTTPException(status_code=503, detail="PostgreSQL non accessible")

    pg = get_pg_connection()
    cur = pg.cursor()
    try:
        cur.execute("""
            SELECT c.id_consultation, c.date_heure, c.agent_id,
                   p.nom_chiffre AS patient_nom,
                   d.maladie_code, d.gravite_score, d.couleur_alerte,
                   ROUND(CAST(d.probabilite_ml * 100 AS NUMERIC), 1) AS proba_pct
            FROM consultations c
            LEFT JOIN patients p ON c.id_patient = p.id_patient
            LEFT JOIN diagnostics d ON c.id_consultation = d.id_consultation
            ORDER BY c.date_heure DESC
            LIMIT 10
        """)
        rows = cur.fetchall()
        consultations = []
        for row in rows:
            date_val = row[1]
            consultations.append({
                "id": row[0],
                "date": date_val.isoformat() if hasattr(date_val, 'isoformat') else str(date_val),
                "agent_id": row[2],
                "patient_nom": row[3],
                "diagnostic": row[4],
                "gravite": row[5],
                "couleur": row[6],
                "proba": float(row[7]) if row[7] is not None else None
            })
        return {"consultations": consultations, "source": "postgresql"}
    finally:
        cur.close()
        pg.close()


@app.get("/api/v1/agents")
async def get_agents():
    """Retourne la liste des agents depuis PostgreSQL."""
    from src.database.postgres_sync import get_pg_connection, test_pg_connection

    default_agents = [
        {"id": "agent_aminatou", "nom": "Aminatou Wali", "role": "Infirmière", "etablissement": "CMA Ngaoundéré"},
        {"id": "agent_ibrahim", "nom": "Ibrahim Hamadou", "role": "Agent de santé", "etablissement": "CMA Ngaoundéré"}
    ]

    if not test_pg_connection():
        return {"agents": default_agents, "source": "local"}

    pg = get_pg_connection()
    cur = pg.cursor()
    try:
        cur.execute("""
            SELECT a.id_agent, a.nom_complet, a.role,
                   e.nom AS etablissement
            FROM agents a
            LEFT JOIN etablissements e ON a.id_etablissement = e.id_etablissement
            ORDER BY a.nom_complet
        """)
        rows = cur.fetchall()
        if not rows:
            return {"agents": default_agents, "source": "local"}
        agents = [
            {"id": r[0], "nom": r[1], "role": r[2], "etablissement": r[3]}
            for r in rows
        ]
        return {"agents": agents, "source": "postgresql"}
    finally:
        cur.close()
        pg.close()


@app.post("/api/v1/agents/new")
async def create_agent(data: dict):
    """Crée un nouvel agent dans PostgreSQL."""
    from src.database.postgres_sync import get_pg_connection, test_pg_connection

    nom = data.get("nom", "").strip()
    role = data.get("role", "Agent de santé").strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le champ 'nom' est requis")

    agent_id = "agent_" + nom.lower().replace(" ", "_").replace("'", "")

    if not test_pg_connection():
        raise HTTPException(status_code=503, detail="PostgreSQL non accessible")

    pg = get_pg_connection()
    cur = pg.cursor()
    try:
        cur.execute("SELECT id_etablissement FROM etablissements WHERE code = 'CMA_NGAOUNDERE_01' LIMIT 1")
        row = cur.fetchone()
        etab_id = row[0] if row else None

        cur.execute(
            """INSERT INTO agents (id_agent, nom_complet, role, id_etablissement)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (id_agent) DO UPDATE SET
                   nom_complet = EXCLUDED.nom_complet,
                   role = EXCLUDED.role""",
            (agent_id, nom, role, etab_id)
        )
        pg.commit()
        return {"agent_id": agent_id, "nom": nom, "role": role, "message": "Agent créé avec succès"}
    finally:
        cur.close()
        pg.close()


@app.post("/api/v1/sync/trigger")
async def trigger_sync():
    """Déclenche une synchronisation réelle vers PostgreSQL."""
    from src.database.postgres_sync import sync_to_postgres, test_pg_connection
    db = get_db()
    key = get_key()

    if not test_pg_connection():
        return {
            "success": False,
            "synced_count": 0,
            "errors": ["PostgreSQL non accessible — vérifier la connexion réseau"],
            "message": "Synchronisation impossible : serveur district indisponible"
        }

    result = sync_to_postgres(db, key)

    return {
        "success": result["success"],
        "synced_count": result["synced_consultations"] + result["synced_patients"],
        "synced_consultations": result["synced_consultations"],
        "synced_patients": result["synced_patients"],
        "errors": result["errors"],
        "message": "Synchronisation réussie vers PostgreSQL" if result["success"] else "Synchronisation partielle"
    }


# ---- Redirection racine vers le frontend ----
@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/app/screens/e1_login.html")


# ---- Serveur frontend (prototype HTML) ----
_PROTOTYPE_DIR = Path(__file__).parent.parent.parent / "prototype"
if _PROTOTYPE_DIR.exists():
    app.mount("/app", StaticFiles(directory=_PROTOTYPE_DIR, html=True), name="frontend")
