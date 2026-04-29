"""
Tests unitaires  API FastAPI HealthGuard IA.
Couvre : health check, création patient, diagnostic, sync.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from src.api.app import app, _db, _encryption_key


@pytest.fixture(scope="module")
def client():
    """Client de test FastAPI partagé."""
    return TestClient(app)


@pytest.fixture(scope="module")
def patient_id(client):
    """Crée un patient de test et retourne son ID."""
    response = client.post("/api/v1/patients/new", json={
        "nom": "Aminatou Test",
        "date_naissance": "1990-05-15",
        "sexe": "F",
        "village_code": "NGD_001"
    })
    assert response.status_code == 200
    return response.json()["patient_id"]


class TestHealthEndpoint:
    """Tests de l'endpoint /health."""

    def test_health_ok(self, client):
        """GET /health retourne status ok."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "db_status" in data


class TestPinEndpoints:
    """Tests des endpoints de securite PIN."""

    def test_hash_pin_endpoint(self, client):
        response = client.post("/api/v1/security/pin/hash", json={"pin": "246810"})
        assert response.status_code == 200
        data = response.json()
        assert "pin_hash" in data
        assert isinstance(data["pin_hash"], str)

    def test_verify_pin_endpoint(self, client):
        hashed = client.post("/api/v1/security/pin/hash", json={"pin": "246810"}).json()["pin_hash"]
        response = client.post(
            "/api/v1/security/pin/verify",
            json={"pin": "246810", "stored_hash": hashed},
        )
        assert response.status_code == 200
        assert response.json()["valid"] is True

    def test_hash_pin_rejects_simple_sequence(self, client):
        response = client.post("/api/v1/security/pin/hash", json={"pin": "123456"})
        assert response.status_code == 400


class TestPatientEndpoints:
    """Tests des endpoints patients."""

    def test_create_patient_success(self, client):
        """POST /patients/new crée un patient."""
        response = client.post("/api/v1/patients/new", json={
            "nom": "Bertrand Test",
            "sexe": "M",
            "village_code": "BTR_002"
        })
        assert response.status_code == 200
        data = response.json()
        assert "patient_id" in data
        # Vérifier que l'ID est un UUID valide
        uuid.UUID(data["patient_id"])

    def test_get_patient_exists(self, client, patient_id):
        """GET /patients/{id} retourne le dossier patient."""
        response = client.get(f"/api/v1/patients/{patient_id}")
        assert response.status_code == 200
        data = response.json()
        assert "patient" in data
        assert "consultations" in data

    def test_get_patient_not_found(self, client):
        """GET /patients/{id_inexistant} retourne 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/patients/{fake_id}")
        assert response.status_code == 404


class TestDiagnosticEndpoints:
    """Tests des endpoints de diagnostic."""

    def test_diagnostic_new_paludisme(self, client, patient_id):
        """POST /diagnostic/new retourne un diagnostic pour symptômes paludisme."""
        response = client.post("/api/v1/diagnostic/new", json={
            "patient_id": patient_id,
            "agent_id": "agent_001",
            "symptomes": {
                "fievre": 1, "temperature_celsius": 39.5,
                "frissons": 1, "cephalee": 1, "courbatures": 1,
                "age_ans": 30, "poids_kg": 65, "saison_pluie": 1,
                "duree_symptomes_jours": 3
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert "diagnostic_id" in data
        assert "resultat" in data
        assert "recommandation" in data
        assert data["resultat"]["couleur_alerte"] in ("ROUGE", "ORANGE", "VERT")

    def test_diagnostic_new_patient_not_found(self, client):
        """POST /diagnostic/new avec patient inexistant retourne 404."""
        response = client.post("/api/v1/diagnostic/new", json={
            "patient_id": str(uuid.uuid4()),
            "agent_id": "agent_001",
            "symptomes": {"fievre": 1}
        })
        assert response.status_code == 404

    def test_diagnostic_gravite_scale(self, client, patient_id):
        """Gravité entre 0 et 3."""
        response = client.post("/api/v1/diagnostic/new", json={
            "patient_id": patient_id,
            "agent_id": "agent_001",
            "symptomes": {"fievre": 1, "age_ans": 25, "temperature_celsius": 38.5}
        })
        assert response.status_code == 200
        gravite = response.json()["resultat"]["gravite"]
        assert 0 <= gravite <= 3


class TestSyncEndpoints:
    """Tests des endpoints de synchronisation."""

    def test_sync_status(self, client):
        """GET /sync/status retourne le statut."""
        response = client.get("/api/v1/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert "pending_sync_count" in data

    def test_sync_trigger(self, client):
        """POST /sync/trigger retourne une réponse."""
        response = client.post("/api/v1/sync/trigger")
        assert response.status_code == 200
        data = response.json()
        assert "synced_count" in data
