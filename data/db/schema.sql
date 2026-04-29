-- HealthGuard IA  Schéma de Base de Données SQLite
-- Version : 1.0 | Date : 2026-04-26
-- Toutes les données patients sont chiffrées en AES-256-CBC

CREATE TABLE IF NOT EXISTS agents (
    id_agent        TEXT PRIMARY KEY,
    nom             TEXT NOT NULL,
    role            TEXT,
    pin_hash        TEXT,                       -- Hash Argon2id du PIN
    biometric_key   TEXT,                       -- Clé publique WebAuthn (JSON)
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Table des patients (données identifiantes chiffrées)
CREATE TABLE IF NOT EXISTS patients (
    id_patient      TEXT PRIMARY KEY,           -- UUID v4
    nom_chiffre     TEXT NOT NULL,              -- Nom chiffré AES-256
    date_naissance  TEXT,                       -- Format YYYY-MM-DD chiffré
    sexe            TEXT NOT NULL,              -- 'M' ou 'F'
    village_code    TEXT NOT NULL,              -- Code village (non chiffré, pseudo-anonyme)
    created_at      TEXT NOT NULL,              -- ISO 8601 UTC
    updated_at      TEXT NOT NULL               -- ISO 8601 UTC
);

-- Table des consultations
CREATE TABLE IF NOT EXISTS consultations (
    id_consultation TEXT PRIMARY KEY,           -- UUID v4
    id_patient      TEXT NOT NULL,              -- FK -> patients
    date_heure      TEXT NOT NULL,              -- ISO 8601 UTC
    agent_id        TEXT NOT NULL,              -- Identifiant de l'agent de santé
    symptomes_json  TEXT NOT NULL,              -- JSON chiffré des symptômes saisis
    statut_sync     TEXT DEFAULT 'PENDING',     -- PENDING | SYNCED | ERROR
    created_at      TEXT NOT NULL,
    FOREIGN KEY (id_patient) REFERENCES patients(id_patient)
);

-- Table des diagnostics
CREATE TABLE IF NOT EXISTS diagnostics (
    id_diagnostic   TEXT PRIMARY KEY,           -- UUID v4
    id_consultation TEXT NOT NULL,              -- FK -> consultations
    maladie_code    TEXT NOT NULL,              -- Code maladie (paludisme_grave, etc.)
    probabilite_ml  REAL,                       -- Score ML (0.0 à 1.0)
    decision_arbre  TEXT,                       -- Résultat de l'arbre décisionnel
    recommandation_json TEXT NOT NULL,          -- JSON des recommandations (chiffré)
    gravite_score   INTEGER NOT NULL,           -- 0=faible, 1=modéré, 2=élevé, 3=critique
    created_at      TEXT NOT NULL,
    FOREIGN KEY (id_consultation) REFERENCES consultations(id_consultation)
);

-- Table des traitements
CREATE TABLE IF NOT EXISTS traitements (
    id_traitement   TEXT PRIMARY KEY,           -- UUID v4
    id_diagnostic   TEXT NOT NULL,              -- FK -> diagnostics
    medicament_code TEXT NOT NULL,              -- Code médicament (ex: AL_6x1)
    dose            TEXT NOT NULL,              -- Dosage (ex: "1 comprimé 2x/jour")
    duree_jours     INTEGER NOT NULL,           -- Durée en jours
    transfert_requis INTEGER DEFAULT 0,         -- 0=Non, 1=Oui
    created_at      TEXT NOT NULL,
    FOREIGN KEY (id_diagnostic) REFERENCES diagnostics(id_diagnostic)
);

-- Table du journal d'audit (chaîne de hash ininterrompue)
CREATE TABLE IF NOT EXISTS audit_log (
    id_log          TEXT PRIMARY KEY,           -- UUID v4
    user_id         TEXT NOT NULL,              -- Identifiant de l'agent
    action_type     TEXT NOT NULL,              -- LOGIN | CONSULTATION | DIAGNOSTIC | SYNC | etc.
    table_cible     TEXT,                       -- Table concernée
    entite_id       TEXT,                       -- ID de l'entité modifiée
    timestamp       TEXT NOT NULL,              -- ISO 8601 UTC
    hash_payload    TEXT NOT NULL,              -- SHA-256 du contenu de l'action
    hash_precedent  TEXT NOT NULL               -- SHA-256 du log précédent (chaîne)
);

-- Table de la queue de synchronisation
CREATE TABLE IF NOT EXISTS sync_queue (
    id_queue        TEXT PRIMARY KEY,           -- UUID v4
    table_cible     TEXT NOT NULL,              -- Table à synchroniser
    operation       TEXT NOT NULL,              -- INSERT | UPDATE | DELETE
    payload_chiffre TEXT NOT NULL,              -- Données chiffrées en attente
    tentatives      INTEGER DEFAULT 0,          -- Nombre de tentatives de sync
    derniere_tentative TEXT,                    -- Dernière tentative (ISO 8601)
    created_at      TEXT NOT NULL
);

-- Table de référence des maladies (données publiques, non chiffrées)
CREATE TABLE IF NOT EXISTS ref_maladies (
    code_maladie        TEXT PRIMARY KEY,       -- Ex: paludisme_grave
    nom_fr              TEXT NOT NULL,          -- Nom en français
    nom_local           TEXT,                   -- Nom en langue locale (Fulfude/Bulu)
    symptomes_cles_json TEXT NOT NULL,          -- JSON des symptômes clés
    protocole_json      TEXT NOT NULL           -- JSON du protocole de traitement OMS
);

-- Index pour optimiser les requêtes fréquentes
CREATE INDEX IF NOT EXISTS idx_consultations_patient ON consultations(id_patient);
CREATE INDEX IF NOT EXISTS idx_consultations_date ON consultations(date_heure);
CREATE INDEX IF NOT EXISTS idx_diagnostics_consultation ON diagnostics(id_consultation);
CREATE INDEX IF NOT EXISTS idx_diagnostics_maladie ON diagnostics(maladie_code);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_sync_statut ON sync_queue(tentatives);

-- Données de référence initiales
INSERT OR IGNORE INTO ref_maladies VALUES (
    'paludisme_simple',
    'Paludisme simple',
    'Palu (Fulfude: malaria)',
    '["fievre","frissons","cephalee","vomissements","courbatures"]',
    '{"traitement":"artemether_lumefantrine","duree":3,"dose_enfant":"selon_poids","dose_adulte":"4cp_2xj"}'
);
INSERT OR IGNORE INTO ref_maladies VALUES (
    'paludisme_grave',
    'Paludisme grave',
    'Palu grave',
    '["fievre_haute","convulsions","trouble_conscience","vomissements_incoercibles","ictere"]',
    '{"traitement":"transfert_immediat","pre_transfert":"quinine_iv","contre_indication":"AL_oral"}'
);
INSERT OR IGNORE INTO ref_maladies VALUES (
    'ira_pneumonie',
    'Infection Respiratoire Aiguë / Pneumonie',
    'Toux grave',
    '["toux","fievre","dyspnee","tirage_sous_costal","tachypnee"]',
    '{"traitement":"amoxicilline","duree":5,"dose_enfant":"40mg_kg_j","transfert_si_severe":true}'
);
INSERT OR IGNORE INTO ref_maladies VALUES (
    'malnutrition_mas',
    'Malnutrition Aiguë Sévère',
    'Manque nourriture grave',
    '["pb_inf_115","oedemes_bilatx","rapport_PT_inf_70","muac_inf_115"]',
    '{"traitement":"ATPE_Plumpy_Nut","test_appetit":true,"transfert_si_complications":true}'
);
INSERT OR IGNORE INTO ref_maladies VALUES (
    'diarrhee_cholera',
    'Diarrhée aiguë / Choléra suspect',
    'Ventre malade grave',
    '["diarrhee_profuse","vomissements","deshydratation","selles_eau_riz"]',
    '{"traitement":"SRO_ou_Ringer","notification_district":true,"grossesse_surveillance":true}'
);
INSERT OR IGNORE INTO ref_maladies VALUES (
    'tuberculose',
    'Tuberculose pulmonaire',
    'Maladie poumons longue',
    '["toux_3_semaines","hemoptysie","amaigrissement","sueurs_nocturnes"]',
    '{"traitement":"reference_CDTB","pas_ab_empirique":true,"isolement_respiratoire":true}'
);
