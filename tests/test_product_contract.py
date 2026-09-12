import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "services" / "backend"


def test_claim_contract_has_traceability_metadata():
    models = (BACKEND / "app" / "models.py").read_text(encoding="utf-8")
    for field in (
        "evidence_ids",
        "confidence",
        "stability",
        "observed_at",
        "expires_at",
        "sensitivity",
        "user_editable",
        "user_confirmed",
    ):
        assert field in models
    assert "raw content" not in models.lower()


def test_core_data_tables_are_declared():
    models = (BACKEND / "app" / "models.py").read_text(encoding="utf-8")
    tables = {
        "users",
        "consents",
        "raw_documents",
        "evidence",
        "claims",
        "feature_snapshots",
        "pair_features",
        "impressions",
        "actions",
        "matches",
        "conversations",
        "outcomes",
        "safety_events",
        "model_versions",
        "policy_versions",
        "outbox_events",
        "idempotency_keys",
        "audit_logs",
    }
    for table in tables:
        assert f'__tablename__ = "{table}"' in models


def test_recommendation_dto_excludes_internal_order_fields():
    schemas = (BACKEND / "app" / "schemas.py").read_text(encoding="utf-8")
    candidate_start = schemas.index("class CandidateLead")
    candidate_end = schemas.index("class RecommendationBundle")
    candidate_contract = schemas[candidate_start:candidate_end]
    for forbidden in ("ranking_score", "success_probability", "confidence", "explanation_factors"):
        assert forbidden not in candidate_contract
    for required in ("common_signals", "differences", "unknowns", "how_to_continue"):
        assert required in candidate_contract


def test_matching_pipeline_enforces_consent_safety_and_exploration():
    matching = (BACKEND / "app" / "modules" / "matching.py").read_text(encoding="utf-8")
    for required in (
        'has_active_consent(db, viewer.id, "matching:v1")',
        "P1",
        "P11",
        "P12",
        "P13",
        "exploration_slot",
        "model_version",
        "policy_version",
        "consent_scope",
    ):
        assert required in matching


def test_initial_migration_enables_pgvector_and_all_tables():
    migration = next((BACKEND / "migrations" / "versions").glob("*_initial_schema.py"))
    text = migration.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in text
    for table in ("users", "claims", "impressions", "outcomes", "safety_events"):
        assert re.search(rf'op\.create_table\(\s*"{table}"', text)


def test_compose_declares_required_local_services():
    compose = (ROOT / "infra" / "compose" / "docker-compose.yml").read_text(encoding="utf-8")
    for service in ("postgres:", "redis:", "backend:", "worker:", "web:"):
        assert service in compose
    assert "pgvector/pgvector" in compose


def test_openapi_contract_exposes_required_v1_flows():
    import json

    spec = json.loads(
        (ROOT / "packages" / "contracts" / "openapi.json").read_text(encoding="utf-8")
    )
    required = (
        "/api/v1/auth/register",
        "/api/v1/consents",
        "/api/v1/questionnaire/submissions",
        "/api/v1/recommendations",
        "/api/v1/invitations",
        "/api/v1/outcomes",
        "/api/v1/safety/reports",
        "/api/v1/privacy/me",
    )
    for route in required:
        assert route in spec["paths"]
