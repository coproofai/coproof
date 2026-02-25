from app.models.graph_index import GraphNode
from app import db
import uuid

def test_graph_node_creation():
    project_id = uuid.uuid4()
    statement_id = uuid.uuid4()
    parent_statement_id = uuid.uuid4()

    node = GraphNode(
        project_id=project_id,
        title="Test Theorem",
        node_type="theorem",
        statement_id=statement_id,
        parent_statement_id=parent_statement_id,
        lean_relative_path="statements/1234.lean",
        latex_relative_path="statements/1234.tex"
    )

    db.session.add(node)
    db.session.commit()

    # Fetch the created node and verify its fields
    created_node = GraphNode.query.get(node.id)
    assert created_node.statement_id == statement_id
    assert created_node.parent_statement_id == parent_statement_id
    assert created_node.lean_relative_path == "statements/1234.lean"
    assert created_node.latex_relative_path == "statements/1234.tex"