"""Database model metadata checks that do not require a live database."""

from app.models import Base


EXPECTED_TABLES = {
    "roles", "users", "departments", "categories", "tickets", "ticket_comments",
    "ticket_attachments", "ticket_status_history", "ticket_assignments", "ticket_feedback",
    "ticket_duplicates", "sla_rules", "notifications", "audit_logs",
    "knowledge_documents", "knowledge_chunks",
}


def test_all_domain_models_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_vector_columns_have_expected_dimension() -> None:
    assert Base.metadata.tables["tickets"].c.embedding.type.dim == 384
    assert Base.metadata.tables["knowledge_chunks"].c.embedding.type.dim == 384


def test_feedback_ticket_constraint_is_unique() -> None:
    constraints = Base.metadata.tables["ticket_feedback"].constraints
    assert any(constraint.name == "uq_ticket_feedback_ticket_id" for constraint in constraints)