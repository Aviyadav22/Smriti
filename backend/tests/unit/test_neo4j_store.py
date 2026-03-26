"""Tests for Neo4j store input validation."""
import pytest
from app.core.providers.graph.neo4j_store import _validate_label, _validate_relationship


def test_validate_label_accepts_known():
    assert _validate_label("Case") == "Case"
    assert _validate_label("Statute") == "Statute"


def test_validate_label_rejects_unknown():
    with pytest.raises(ValueError, match="Invalid node label"):
        _validate_label("Case) DETACH DELETE n //")


def test_validate_label_rejects_injection():
    with pytest.raises(ValueError):
        _validate_label("Case}-[:HACKED]->(x) DELETE x WITH x MATCH (n:{label:")


def test_validate_relationship_accepts_known():
    assert _validate_relationship("CITES") == "CITES"
    assert _validate_relationship("EQUIVALENT_TO") == "EQUIVALENT_TO"
    assert _validate_relationship("APPLIES_PRINCIPLE") == "APPLIES_PRINCIPLE"


def test_validate_relationship_rejects_injection():
    with pytest.raises(ValueError):
        _validate_relationship("CITES] DETACH DELETE n WITH n MATCH (m)-[r:")


def test_validate_relationship_rejects_unknown():
    with pytest.raises(ValueError, match="Invalid relationship"):
        _validate_relationship("DROP_DATABASE")
