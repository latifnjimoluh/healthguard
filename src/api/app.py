"""
Application FastAPI principale pour HealthGuard IA.
API REST locale pour le moteur de diagnostic et la gestion des patients.
"""

import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.database.encryption import decrypt_field, encrypt_field, generate_key
from src.database.schema import DEFAULT_DB_PATH, initialize_database
from src.database.sync import add_to_sync_queue, get_sync_status
from src.database.audit import log_action
from src.decision_engine.aggregator import aggregate
from src.decision_engine.recommendation import generate_recommendation
from src.decision_engine.severity_scorer import calculate_severity_score
from src.security.pin_auth import check_pin_complexity, hash_pin, verify_pin

load_dotenv(Path(__file__).parent.parent.parent / ".env")


app = FastAPI(
    title="HealthGuard IA API",
    description="API de diagnostic médical offline pour zones rurales - Cameroun",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_db = None
_encryption_key = None


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
    sexe: Optional[str] = None
    village_code: Optional[str] = None
    patient_id: Optional[str] = None


class ConsultationBrowser(BaseModel):
    date: Optional[str] = None
    patient_nom: Optional[str] = None
    patient_id: Optional[str] = None
    agent_id: Optional[str] = None
    age_ans: Optional[float] = None
    sexe: Optional[str] = None
    village_code: Optional[str] = None
    poids_kg: Optional[float] = None
    diagnostic: Optional[str] = None
    code: Optional[str] = None
    gravite: Optional[int] = None
    couleur: Optional[str] = None
    proba: Optional[float] = None
    decision_arbre: Optional[str] = None
    recommandation: Optional[dict] = None
    symptomes: Optional[dict] = None
    synced: Optional[bool] = False
    consultation_id: Optional[str] = None
    diagnostic_id: Optional[str] = None


class SyncFromBrowserInput(BaseModel):
    consultations: List[ConsultationBrowser] = []
    agent_id: Optional[str] = None


class PinHashInput(BaseModel):
    pin: str


class PinVerifyInput(BaseModel):
    pin: str
    stored_hash: str


class PinChangeInput(BaseModel):
    agent_id: str
    old_pin: str
    new_pin: str


class BiometricRegisterInput(BaseModel):
    agent_id: str
    public_key_json: str


class BiometricLoginInput(BaseModel):
    agent_id: str
    credential_id: str


class AgentNew(BaseModel):
    nom: str
    role: Optional[str] = "Agent de sante"
    pin: Optional[str] = None


class PatientListItem(BaseModel):
    id: str
    nom: str
    sexe: Optional[str] = None
    village_code: Optional[str] = None
    date_naissance: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    consultation_count: int = 0
    last_consultation_at: Optional[str] = None


def get_db():
    """Fournit la connexion SQLite persistante."""
    global _db
    if _db is None:
        _db = initialize_database(str(DEFAULT_DB_PATH))
    return _db


def get_key():
    """
    Fournit une clé de chiffrement stable entre redémarrages.
    """
    global _encryption_key
    if _encryption_key is None:
        pin = os.getenv("HEALTHGUARD_LOCAL_PIN")
        if not pin:
            # En développement, on accepte un fallback mais on avertit
            # En production (réelle), cela devrait lever une erreur ou forcer une config
            pin = "123456"
            print("WARNING: HEALTHGUARD_LOCAL_PIN non defini, utilisation du code par defaut (INSECURE)")
        
        salt_text = os.getenv("HEALTHGUARD_ENCRYPTION_SALT", "healthguard_local_salt_v1")
        salt = salt_text.encode("utf-8")[:32].ljust(32, b"0")
        _encryption_key = generate_key(pin, salt)
    return _encryption_key


def _age_to_birthdate(age_ans: Optional[float]) -> Optional[str]:
    if age_ans is None:
        return None
    year = date.today().year - int(age_ans)
    return f"{year}-01-01"


def _normalize_sexe(sexe: Optional[str]) -> Optional[str]:
    if not sexe:
        return None
    sexe = sexe.upper().strip()
    return sexe if sexe in {"M", "F"} else None


def _normalize_village_code(village_code: Optional[str]) -> str:
    code = (village_code or "").strip()
    return code or "NON_SPECIFIE"


def _safe_patient_display_name(nom_chiffre: str, key: bytes) -> str:
    try:
        return decrypt_field(nom_chiffre, key)
    except Exception:
        return nom_chiffre


def _queue_patient_sync(db, key: bytes, payload: dict) -> str:
    return add_to_sync_queue("patients", "UPSERT", payload, key, db)


def _queue_consultation_sync(db, key: bytes, payload: dict) -> str:
    return add_to_sync_queue("consultations", "UPSERT", payload, key, db)


def _persist_patient(
    db,
    key: bytes,
    *,
    patient_id: Optional[str],
    nom: str,
    date_naissance: Optional[str],
    sexe: Optional[str],
    village_code: Optional[str],
    agent_id: str = "system",
) -> tuple[str, str]:
    timestamp = datetime.now(timezone.utc).isoformat()
    final_patient_id = patient_id or str(uuid.uuid4())
    
    # Chiffrement de TOUS les champs identifiants (Audit Fix)
    encrypted_name = encrypt_field(nom, key)
    encrypted_birth = encrypt_field(date_naissance, key) if date_naissance else None
    encrypted_sexe = encrypt_field(_normalize_sexe(sexe), key) if sexe else None
    encrypted_village = encrypt_field(_normalize_village_code(village_code), key) if village_code else None

    existing = db.execute(
        "SELECT id_patient FROM patients WHERE id_patient = ?",
        (final_patient_id,),
    ).fetchone()

    if existing:
        db.execute(
            """UPDATE patients
               SET nom_chiffre = ?, date_naissance = COALESCE(?, date_naissance),
                   sexe = COALESCE(?, sexe), village_code = COALESCE(?, village_code),
                   updated_at = ?
               WHERE id_patient = ?""",
            (
                encrypted_name,
                encrypted_birth,
                encrypted_sexe,
                encrypted_village,
                timestamp,
                final_patient_id,
            ),
        )
        created_at_row = db.execute(
            "SELECT created_at FROM patients WHERE id_patient = ?",
            (final_patient_id,),
        ).fetchone()
        created_at = created_at_row["created_at"]
        log_action(agent_id, "UPDATE_PATIENT", "patients", final_patient_id, db)
    else:
        created_at = timestamp
        db.execute(
            """INSERT INTO patients
               (id_patient, nom_chiffre, date_naissance, sexe, village_code, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                final_patient_id,
                encrypted_name,
                encrypted_birth,
                encrypted_sexe,
                encrypted_village,
                created_at,
                timestamp,
            ),
        )
        log_action(agent_id, "CREATE_PATIENT", "patients", final_patient_id, db)

    patient_payload = {
        "id_patient": final_patient_id,
        "nom_chiffre": encrypted_name,
        "date_naissance": encrypted_birth,
        "sexe": encrypted_sexe,
        "village_code": encrypted_village,
        "created_at": created_at,
        "updated_at": timestamp,
    }
    _queue_patient_sync(db, key, patient_payload)
    db.commit()
    return final_patient_id, encrypted_name


def _persist_consultation_and_diagnostic(
    db,
    key: bytes,
    *,
    patient_id: str,
    agent_id: str,
    symptomes: dict,
    resultat,
    recommandation,
    consultation_id: Optional[str] = None,
    diagnostic_id: Optional[str] = None,
    date_heure: Optional[str] = None,
) -> dict:
    ts = date_heure or datetime.now(timezone.utc).isoformat()
    final_consultation_id = consultation_id or str(uuid.uuid4())
    final_diagnostic_id = diagnostic_id or str(uuid.uuid4())

    symptomes_chiffre = encrypt_field(json.dumps(symptomes, ensure_ascii=False), key)
    recommandation_json = {
        "resume_3_points": recommandation.resume_3_points,
        "detail_complet": recommandation.detail_complet,
        "medicaments": recommandation.medicaments,
        "transfert": recommandation.transfert,
        "notification_district": recommandation.notification_district,
        "contre_indications": recommandation.contre_indications,
        "suivi_recommande": recommandation.suivi_recommande,
        "action_immediate": recommandation.action_immediate,
        "couleur_alerte": recommandation.couleur_alerte,
    }
    recommandation_chiffre = encrypt_field(json.dumps(recommandation_json, ensure_ascii=False), key)

    existing_consult = db.execute(
        "SELECT id_consultation, created_at FROM consultations WHERE id_consultation = ?",
        (final_consultation_id,),
    ).fetchone()
    consultation_created_at = existing_consult["created_at"] if existing_consult else ts

    if existing_consult:
        db.execute(
            """UPDATE consultations
               SET id_patient = ?, date_heure = ?, agent_id = ?, symptomes_json = ?,
                   statut_sync = 'PENDING'
               WHERE id_consultation = ?""",
            (patient_id, ts, agent_id, symptomes_chiffre, final_consultation_id),
        )
    else:
        db.execute(
            """INSERT INTO consultations
               (id_consultation, id_patient, date_heure, agent_id, symptomes_json, statut_sync, created_at)
               VALUES (?, ?, ?, ?, ?, 'PENDING', ?)""",
            (
                final_consultation_id,
                patient_id,
                ts,
                agent_id,
                symptomes_chiffre,
                consultation_created_at,
            ),
        )

    existing_diag = db.execute(
        "SELECT id_diagnostic, created_at FROM diagnostics WHERE id_diagnostic = ?",
        (final_diagnostic_id,),
    ).fetchone()
    diagnostic_created_at = existing_diag["created_at"] if existing_diag else ts

    if existing_diag:
        db.execute(
            """UPDATE diagnostics
               SET maladie_code = ?, probabilite_ml = ?, decision_arbre = ?,
                   recommandation_json = ?, gravite_score = ?
               WHERE id_diagnostic = ?""",
            (
                resultat.diagnostic_principal,
                float(resultat.probabilite_combinee),
                resultat.source_decision,
                recommandation_chiffre,
                resultat.gravite,
                final_diagnostic_id,
            ),
        )
    else:
        db.execute(
            """INSERT INTO diagnostics
               (id_diagnostic, id_consultation, maladie_code, probabilite_ml,
                decision_arbre, recommandation_json, gravite_score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                final_diagnostic_id,
                final_consultation_id,
                resultat.diagnostic_principal,
                float(resultat.probabilite_combinee),
                resultat.source_decision,
                recommandation_chiffre,
                resultat.gravite,
                diagnostic_created_at,
            ),
        )

    consultation_payload = {
        "id_consultation": final_consultation_id,
        "id_patient": patient_id,
        "date_heure": ts,
        "agent_id": agent_id,
        "symptomes_json": symptomes_chiffre,
        "created_at": consultation_created_at,
        "diagnostic": {
            "id_diagnostic": final_diagnostic_id,
            "maladie_code": resultat.diagnostic_principal,
            "probabilite_ml": float(resultat.probabilite_combinee),
            "decision_arbre": resultat.source_decision,
            "recommandation_json": recommandation_chiffre,
            "gravite_score": resultat.gravite,
            "couleur_alerte": resultat.couleur_alerte,
            "created_at": diagnostic_created_at,
        },
    }
    _queue_consultation_sync(db, key, consultation_payload)
    
    # Persistance explicite des traitements (Audit Fix)
    medicaments = recommandation_json.get("medicaments", [])
    for med in medicaments:
        traitement_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO traitements
               (id_traitement, id_diagnostic, medicament_code, dose, duree_jours, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                traitement_id,
                final_diagnostic_id,
                med.get("nom", "inconnu"),
                med.get("dosage", "N/A"),
                med.get("duree", 0),
                ts,
            ),
        )

    log_action(agent_id, "CONSULTATION_DIAGNOSTIC", "consultations", final_consultation_id, db)
    db.commit()

    return {
        "consultation_id": final_consultation_id,
        "diagnostic_id": final_diagnostic_id,
        "consultation_created_at": consultation_created_at,
        "diagnostic_created_at": diagnostic_created_at,
        "recommandation_json": recommandation_json,
    }


def _build_result_from_browser_item(item: ConsultationBrowser):
    class BrowserResult:
        diagnostic_principal = item.code or item.diagnostic or "indetermine"
        probabilite_combinee = round((item.proba or 50) / 100, 3)
        gravite = item.gravite or 1
        source_decision = item.decision_arbre or "browser_import"
        couleur_alerte = (item.couleur or "ORANGE").upper()

    class BrowserRecommendation:
        couleur_alerte = (item.couleur or "ORANGE").upper()
        action_immediate = (item.recommandation or {}).get("action_immediate", "EVALUATION_CLINIQUE")
        resume_3_points = (item.recommandation or {}).get("points", ["Import navigateur"])
        detail_complet = (item.recommandation or {}).get("detail_complet", "Consultation importee depuis le navigateur.")
        medicaments = (item.recommandation or {}).get("traitement", [])
        contre_indications = (item.recommandation or {}).get("contre_indications", [])
        transfert = (item.recommandation or {}).get("transfert")
        notification_district = (item.recommandation or {}).get("notification_district", False)
        suivi_recommande = (item.recommandation or {}).get("suivi", [])

    return BrowserResult(), BrowserRecommendation()


@app.get("/api/v1/health")
async def health_check():
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
        "version": "1.1.0",
        "model_loaded": model_loaded,
        "db_status": db_status,
        "storage_mode": "sqlite_file",
        "db_path": str(DEFAULT_DB_PATH),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/security/pin/hash")
async def pin_hash_endpoint(data: PinHashInput):
    if not check_pin_complexity(data.pin):
        raise HTTPException(status_code=400, detail="PIN trop simple")
    return {"pin_hash": hash_pin(data.pin)}


@app.post("/api/v1/security/pin/verify")
async def pin_verify_endpoint(data: PinVerifyInput):
    return {"valid": verify_pin(data.pin, data.stored_hash)}


@app.post("/api/v1/diagnostic/new")
async def new_diagnostic(data: SymptomesInput):
    db = get_db()
    key = get_key()

    patient = db.execute(
        "SELECT id_patient FROM patients WHERE id_patient = ?",
        (data.patient_id,),
    ).fetchone()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {data.patient_id} non trouvé")

    severity = calculate_severity_score(data.symptomes)

    try:
        resultat = aggregate(data.symptomes)
        recommandation = generate_recommendation(resultat)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur moteur diagnostic : {exc}") from exc

    persisted = _persist_consultation_and_diagnostic(
        db,
        key,
        patient_id=data.patient_id,
        agent_id=data.agent_id,
        symptomes=data.symptomes,
        resultat=resultat,
        recommandation=recommandation,
    )

    return {
        "diagnostic_id": persisted["diagnostic_id"],
        "consultation_id": persisted["consultation_id"],
        "resultat": {
            "diagnostic": resultat.diagnostic_principal,
            "probabilite": round(resultat.probabilite_combinee * 100, 1),
            "gravite": resultat.gravite,
            "couleur_alerte": resultat.couleur_alerte,
            "diagnostic_differentiel": resultat.diagnostic_differentiel,
            "proba_differentiel": round(resultat.proba_differentiel * 100, 1)
            if resultat.diagnostic_differentiel
            else None,
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
            "suivi_recommande": recommandation.suivi_recommande,
        },
        "severity_score": severity,
    }


@app.post("/api/v1/diagnostic/tree-step")
async def tree_step(data: TreeStepInput):
    return {
        "session_id": data.session_id,
        "noeud_id": data.noeud_id,
        "reponse_enregistree": data.reponse,
        "message": "Etape enregistree - appeler /diagnostic/new avec tous les symptomes",
    }


@app.post("/api/v1/patients/new")
async def create_patient(data: NouveauPatient):
    db = get_db()
    key = get_key()

    patient_id, _ = _persist_patient(
        db,
        key,
        patient_id=data.patient_id,
        nom=data.nom,
        date_naissance=data.date_naissance,
        sexe=data.sexe,
        village_code=data.village_code,
        agent_id="unknown_agent",  # TODO: Récupérer l'ID de l'agent connecté
    )

    return {
        "patient_id": patient_id,
        "message": "Patient cree avec succes",
    }


@app.get("/api/v1/patients/{patient_id}")
async def get_patient(patient_id: str):
    db = get_db()
    key = get_key()

    patient = db.execute(
        "SELECT * FROM patients WHERE id_patient = ?",
        (patient_id,),
    ).fetchone()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient non trouvé")

    consultations = db.execute(
        """SELECT c.id_consultation, c.date_heure, c.agent_id, c.statut_sync,
                  d.maladie_code, d.gravite_score, d.probabilite_ml
           FROM consultations c
           LEFT JOIN diagnostics d ON c.id_consultation = d.id_consultation
           WHERE c.id_patient = ?
           ORDER BY c.date_heure DESC""",
        (patient_id,),
    ).fetchall()

    return {
        "patient": {
            "id": patient_id,
            "nom": _safe_patient_display_name(patient["nom_chiffre"], key),
            "sexe": decrypt_field(patient["sexe"], key) if patient["sexe"] else None,
            "village_code": decrypt_field(patient["village_code"], key) if patient["village_code"] else None,
            "date_naissance": decrypt_field(patient["date_naissance"], key) if patient["date_naissance"] else None,
            "created_at": patient["created_at"],
        },
        "consultations": [dict(row) for row in consultations],
    }


@app.get("/api/v1/patients")
async def list_patients():
    db = get_db()
    key = get_key()
    rows = db.execute(
        """SELECT p.id_patient, p.nom_chiffre, p.sexe, p.village_code,
                  p.date_naissance, p.created_at, p.updated_at,
                  COUNT(c.id_consultation) AS consultation_count,
                  MAX(c.date_heure) AS last_consultation_at
           FROM patients p
           LEFT JOIN consultations c ON c.id_patient = p.id_patient
           GROUP BY p.id_patient, p.nom_chiffre, p.sexe, p.village_code,
                    p.date_naissance, p.created_at, p.updated_at
           ORDER BY COALESCE(MAX(c.date_heure), p.updated_at, p.created_at) DESC"""
    ).fetchall()
    patients = []
    for row in rows:
        patients.append(
            {
                "id": row["id_patient"],
                "nom": _safe_patient_display_name(row["nom_chiffre"], key),
                "sexe": decrypt_field(row["sexe"], key) if row["sexe"] else None,
                "village_code": decrypt_field(row["village_code"], key) if row["village_code"] else None,
                "date_naissance": decrypt_field(row["date_naissance"], key) if row["date_naissance"] else None,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "consultation_count": row["consultation_count"],
                "last_consultation_at": row["last_consultation_at"],
            }
        )
    return {"patients": patients}


@app.get("/api/v1/sync/status")
async def sync_status():
    from src.database.postgres_sync import test_pg_connection

    db = get_db()
    status = get_sync_status(db)
    pg_ok = test_pg_connection()
    return {
        **status,
        "connexion_status": "online" if pg_ok else "offline",
        "postgres_disponible": pg_ok,
    }


@app.post("/api/v1/sync/from-browser")
async def sync_from_browser(data: SyncFromBrowserInput):
    """
    Import de secours depuis le navigateur vers la SQLite locale.

    Ce flux n'envoie plus directement les données vers PostgreSQL.
    Il alimente la même base locale et la même queue que le reste de l'application,
    puis la synchronisation réelle se fait via /api/v1/sync/trigger.
    """

    db = get_db()
    key = get_key()

    if not data.consultations:
        return {"success": True, "imported": 0, "message": "Aucune donnée à importer"}

    imported = 0
    errors = []

    for item in data.consultations:
        try:
            agent_id = item.agent_id or data.agent_id or "prototype"
            patient_id = item.patient_id or str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{item.patient_nom or 'anonyme'}-{item.age_ans or 'na'}-{item.sexe or 'na'}",
                )
            )
            _persist_patient(
                db,
                key,
                patient_id=patient_id,
                nom=item.patient_nom or "Anonyme",
                date_naissance=_age_to_birthdate(item.age_ans),
                sexe=item.sexe,
                village_code=item.village_code,
                agent_id=agent_id,
            )
            browser_result, browser_recommendation = _build_result_from_browser_item(item)
            _persist_consultation_and_diagnostic(
                db,
                key,
                patient_id=patient_id,
                agent_id=agent_id,
                symptomes=item.symptomes or {},
                resultat=browser_result,
                recommandation=browser_recommendation,
                consultation_id=item.consultation_id,
                diagnostic_id=item.diagnostic_id,
                date_heure=item.date,
            )
            imported += 1
        except Exception as exc:
            errors.append(f"{item.patient_nom or 'inconnu'}: {exc}")

    return {
        "success": len(errors) == 0,
        "imported": imported,
        "errors": errors,
        "message": f"{imported} consultation(s) importee(s) dans la base locale",
    }


@app.get("/api/v1/audit/verify")
async def verify_audit():
    from src.database.audit import verify_chain_integrity
    db = get_db()
    result = verify_chain_integrity(db)
    if not result["valid"]:
        return result # On renvoie le détail de l'erreur
    return result

@app.get("/api/v1/consultations/recent")
async def get_recent_consultations():
    from src.database.postgres_sync import get_pg_connection, test_pg_connection

    if not test_pg_connection():
        raise HTTPException(status_code=503, detail="PostgreSQL non accessible")

    pg = get_pg_connection()
    cur = pg.cursor()
    key = get_key()
    try:
        cur.execute(
            """
            SELECT c.id_consultation, c.date_heure, c.agent_id,
                   p.nom_chiffre AS patient_nom,
                   d.maladie_code, d.gravite_score, d.couleur_alerte,
                   ROUND(CAST(d.probabilite_ml * 100 AS NUMERIC), 1) AS proba_pct
            FROM consultations c
            LEFT JOIN patients p ON c.id_patient = p.id_patient
            LEFT JOIN diagnostics d ON c.id_consultation = d.id_consultation
            ORDER BY c.date_heure DESC
            LIMIT 10
            """
        )
        rows = cur.fetchall()
        consultations = []
        for row in rows:
            date_val = row[1]
            consultations.append(
                {
                    "id": row[0],
                    "date": date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val),
                    "agent_id": row[2],
                    "patient_nom": _safe_patient_display_name(row[3], key) if row[3] else "Inconnu",
                    "diagnostic": row[4],
                    "gravite": row[5],
                    "couleur": row[6],
                    "proba": float(row[7]) if row[7] is not None else None,
                }
            )
        return {"consultations": consultations, "source": "postgresql"}
    finally:
        cur.close()
        pg.close()


@app.get("/api/v1/agents")
async def get_agents():
    from src.database.postgres_sync import get_pg_connection, test_pg_connection

    db = get_db()
    # On recupere les agents locaux (avec leur pin_hash)
    local_rows = db.execute("SELECT id_agent, nom, role, pin_hash FROM agents").fetchall()
    local_agents = {
        row["id_agent"]: {"id": row["id_agent"], "nom": row["nom"], "role": row["role"], "pin_hash": row["pin_hash"]}
        for row in local_rows
    }

    default_agents = [
        {"id": "agent_aminatou", "nom": "Aminatou Wali", "role": "Infirmiere", "etablissement": "CMA Ngaoundere"},
        {"id": "agent_ibrahim", "nom": "Ibrahim Hamadou", "role": "Agent de sante", "etablissement": "CMA Ngaoundere"},
    ]

    # Si on n'a aucun agent local, on initialise avec les par defaut
    if not local_agents:
        for a in default_agents:
            # On cree un pin_hash par defaut si on peut (ex: 246810 pour aminatou, 135791 pour ibrahim)
            d_pin = "246810" if a["id"] == "agent_aminatou" else "135791"
            h = hash_pin(d_pin)
            ts = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT OR IGNORE INTO agents (id_agent, nom, role, pin_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (a["id"], a["nom"], a["role"], h, ts, ts)
            )
        db.commit()
        # On relit
        local_rows = db.execute("SELECT id_agent, nom, role, pin_hash FROM agents").fetchall()
        local_agents = {
            row["id_agent"]: {"id": row["id_agent"], "nom": row["nom"], "role": row["role"], "pin_hash": row["pin_hash"]}
            for row in local_rows
        }

    if not test_pg_connection():
        return {"agents": list(local_agents.values()), "source": "local"}

    pg = get_pg_connection()
    cur = pg.cursor()
    try:
        cur.execute(
            """
            SELECT a.id_agent, a.nom_complet, a.role, e.nom AS etablissement
            FROM agents a
            LEFT JOIN etablissements e ON a.id_etablissement = e.id_etablissement
            ORDER BY a.nom_complet
            """
        )
        rows = cur.fetchall()
        remote_agents = []
        ts = datetime.now(timezone.utc).isoformat()
        for row in rows:
            ag_id, ag_nom, ag_role, etab = row
            remote_agents.append({"id": ag_id, "nom": ag_nom, "role": ag_role, "etablissement": etab})
            # Mise a jour locale si absent (sync descendante legere)
            if ag_id not in local_agents:
                db.execute(
                    "INSERT OR IGNORE INTO agents (id_agent, nom, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (ag_id, ag_nom, ag_role, ts, ts)
                )
        db.commit()
        
        # On fusionne pour renvoyer les pin_hash si presents localement
        final_list = []
        for ra in remote_agents:
            if ra["id"] in local_agents:
                ra["pin_hash"] = local_agents[ra["id"]]["pin_hash"]
            final_list.append(ra)
            
        return {"agents": final_list, "source": "postgresql"}
    finally:
        cur.close()
        pg.close()


@app.post("/api/v1/agents/new")
async def create_agent(data: AgentNew):
    db = get_db()
    
    nom = data.nom.strip()
    role = data.role.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le champ 'nom' est requis")

    agent_id = "agent_" + nom.lower().replace(" ", "_").replace("'", "")
    ts = datetime.now(timezone.utc).isoformat()
    
    # Hachage du PIN si fourni
    h = hash_pin(data.pin) if data.pin else None
    
    # Creation locale
    db.execute(
        """INSERT INTO agents (id_agent, nom, role, pin_hash, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT (id_agent) DO UPDATE SET
               nom = EXCLUDED.nom,
               role = EXCLUDED.role,
               pin_hash = COALESCE(EXCLUDED.pin_hash, pin_hash),
               updated_at = EXCLUDED.updated_at""",
        (agent_id, nom, role, h, ts, ts),
    )
    db.commit()
    log_action("system", "CREATE_AGENT", "agents", agent_id, db)

    # Tentative sync distante (optionnelle ici, sera faite par sync/trigger)
    from src.database.postgres_sync import get_pg_connection, test_pg_connection
    if test_pg_connection():
        pg = get_pg_connection()
        cur = pg.cursor()
        try:
            cur.execute("SELECT id_etablissement FROM etablissements WHERE code = 'CMA_NGAOUNDERE_01' LIMIT 1")
            row = cur.fetchone()
            etab_id = row[0] if row else None
            cur.execute(
                """INSERT INTO agents (id_agent, nom_complet, role, id_etablissement)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id_agent) DO UPDATE SET nom_complet = EXCLUDED.nom_complet, role = EXCLUDED.role""",
                (agent_id, nom, role, etab_id),
            )
            pg.commit()
        finally:
            cur.close()
            pg.close()

    return {"agent_id": agent_id, "nom": nom, "role": role, "message": "Agent cree avec succes"}


@app.post("/api/v1/security/pin/change")
async def change_pin(data: PinChangeInput):
    db = get_db()
    
    # Verif de l'ancien PIN
    row = db.execute("SELECT pin_hash FROM agents WHERE id_agent = ?", (data.agent_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent non trouve")
        
    if not verify_pin(data.old_pin, row["pin_hash"]):
        raise HTTPException(status_code=401, detail="Ancien PIN incorrect")
        
    # Validation du nouveau PIN
    if not check_pin_complexity(data.new_pin):
        raise HTTPException(status_code=400, detail="Nouveau PIN trop simple ou invalide")
        
    # Mise a jour
    new_hash = hash_pin(data.new_pin)
    ts = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE agents SET pin_hash = ?, updated_at = ? WHERE id_agent = ?",
        (new_hash, ts, data.agent_id)
    )
    db.commit()
    log_action(data.agent_id, "CHANGE_PIN", "agents", data.agent_id, db)
    
    return {"success": True, "message": "PIN modifie avec succes"}


@app.get("/api/v1/security/biometric/register/options")
async def get_biometric_options(agent_id: str):
    # Challenge aleatoire pour l'enregistrement
    challenge = str(uuid.uuid4())
    return {
        "challenge": challenge,
        "rp": {"name": "HealthGuard IA", "id": "localhost"},
        "user": {"id": agent_id, "name": agent_id, "displayName": agent_id},
        "pubKeyCredParams": [{"alg": -7, "type": "public-key"}]
    }


@app.post("/api/v1/security/biometric/register/verify")
async def register_biometric(data: BiometricRegisterInput):
    db = get_db()
    ts = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE agents SET biometric_key = ?, updated_at = ? WHERE id_agent = ?",
        (data.public_key_json, ts, data.agent_id)
    )
    db.commit()
    log_action(data.agent_id, "REGISTER_BIOMETRIC", "agents", data.agent_id, db)
    return {"success": True}


@app.get("/api/v1/security/biometric/login/options")
async def get_biometric_login_options(agent_id: str):
    db = get_db()
    row = db.execute("SELECT biometric_key FROM agents WHERE id_agent = ?", (agent_id,)).fetchone()
    if not row or not row["biometric_key"]:
        raise HTTPException(status_code=404, detail="Biometrie non configuree pour cet agent")
    
    return {
        "challenge": str(uuid.uuid4()),
        "allowCredentials": [{"id": agent_id, "type": "public-key"}]
    }


@app.post("/api/v1/security/biometric/login/verify")
async def verify_biometric(data: BiometricLoginInput):
    db = get_db()
    row = db.execute("SELECT biometric_key FROM agents WHERE id_agent = ?", (data.agent_id,)).fetchone()
    if not row or not row["biometric_key"]:
        raise HTTPException(status_code=401, detail="Echec authentification biométrique")
    
    # Dans un vrai flux WebAuthn, on verifierait la signature ici
    # Pour le prototype, on valide le fait que l'agent a la clé
    log_action(data.agent_id, "LOGIN_BIOMETRIC", "agents", data.agent_id, db)
    return {"success": True}


@app.post("/api/v1/sync/trigger")
async def trigger_sync():
    from src.database.postgres_sync import sync_to_postgres, test_pg_connection

    db = get_db()
    key = get_key()

    if not test_pg_connection():
        return {
            "success": False,
            "synced_count": 0,
            "errors": ["PostgreSQL non accessible - verifier la connexion reseau"],
            "message": "Synchronisation impossible : serveur district indisponible",
        }

    result = sync_to_postgres(db, key)
    return {
        "success": result["success"],
        "synced_count": result["synced_consultations"] + result["synced_patients"],
        "synced_consultations": result["synced_consultations"],
        "synced_patients": result["synced_patients"],
        "errors": result["errors"],
        "message": "Synchronisation reussie vers PostgreSQL"
        if result["success"]
        else "Synchronisation partielle",
    }


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/app/screens/e1_login.html")


_PROTOTYPE_DIR = Path(__file__).parent.parent.parent / "prototype"
if _PROTOTYPE_DIR.exists():
    app.mount("/app", StaticFiles(directory=_PROTOTYPE_DIR, html=True), name="frontend")
