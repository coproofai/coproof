# tests/models/test_project.py
import uuid
import pytest
from app.models.project import Project
from app.models.graph_index import GraphNode
from app.models.user import User  # Make sure the User model is imported

@pytest.fixture
def create_user(init_db):
    user = User(
        id=uuid.uuid4(),
        full_name="testuser",
        email="testuser@example.com",
        password_hash="hashedpw"  # Can be dummy for tests
    )
    init_db.add(user)
    init_db.commit()
    return user

@pytest.fixture
def create_project(init_db, create_user):
    project = Project(
        name="Test Project",
        description="Integration test",
        leader_id=create_user.id  # use real user id
    )
    init_db.add(project)
    init_db.commit()
    return project

def test_create_project_and_root_graph_node(init_db, create_project):
    project = create_project
    statement_id = uuid.uuid4()

    # Create the root GraphNode (G1)
    root_node = GraphNode(
        project_id=project.id,
        title="G1",
        node_type="global_goal",
        statement_id=statement_id,
        parent_statement_id=None,
        lean_relative_path=f"statements/{statement_id}.lean",
        latex_relative_path=f"statements/{statement_id}.tex",
        is_resolved=False
    )

    init_db.add(root_node)
    init_db.commit()

    # Check that the GraphNode was created correctly
    saved = GraphNode.query.filter_by(project_id=project.id).first()

    assert saved.statement_id == statement_id
    assert saved.parent_statement_id is None
    assert saved.parent is None

def test_parent_child_relationship(init_db, create_project):
    project = create_project
    statement_id_parent = uuid.uuid4()
    statement_id_child = uuid.uuid4()

    # Create parent node
    parent_node = GraphNode(
        project_id=project.id,
        title="Parent Node",
        node_type="theorem",
        statement_id=statement_id_parent,
        parent_statement_id=None,
        lean_relative_path=f"statements/{statement_id_parent}.lean",
        latex_relative_path=f"statements/{statement_id_parent}.tex",
        is_resolved=False
    )

    init_db.add(parent_node)
    init_db.commit()

    # Create child node that depends on parent
    child_node = GraphNode(
        project_id=project.id,
        title="Child Node",
        node_type="lemma",
        statement_id=statement_id_child,
        parent_statement_id=statement_id_parent,  # Linking to parent node
        lean_relative_path=f"statements/{statement_id_child}.lean",
        latex_relative_path=f"statements/{statement_id_child}.tex",
        is_resolved=False
    )

    init_db.add(child_node)
    init_db.commit()

    # Fetch child node and assert that the parent is linked
    child_node = GraphNode.query.filter_by(statement_id=statement_id_child).first()
    assert child_node.parent_statement_id == statement_id_parent

def test_statement_id_unique_per_project(init_db, create_project):
    project = create_project
    statement_id = uuid.uuid4()

    # Create first GraphNode
    node_1 = GraphNode(
        project_id=project.id,
        title="Node 1",
        node_type="theorem",
        statement_id=statement_id,
        parent_statement_id=None,
        lean_relative_path=f"statements/{statement_id}.lean",
        latex_relative_path=f"statements/{statement_id}.tex",
        is_resolved=False
    )

    init_db.add(node_1)
    init_db.commit()

    # Try to create another node with the same statement_id (should raise IntegrityError)
    node_2 = GraphNode(
        project_id=project.id,
        title="Node 2",
        node_type="lemma",
        statement_id=statement_id,
        parent_statement_id=None,
        lean_relative_path=f"statements/{statement_id}.lean",
        latex_relative_path=f"statements/{statement_id}.tex",
        is_resolved=False
    )

    init_db.add(node_2)

    # Assert IntegrityError is raised
    with pytest.raises(Exception):
        init_db.commit()

def test_resolution_fields(init_db, create_project):
    project = create_project
    statement_id_parent = uuid.uuid4()
    statement_id_child = uuid.uuid4()

    # Create parent node
    parent_node = GraphNode(
        project_id=project.id,
        title="Parent Node",
        node_type="theorem",
        statement_id=statement_id_parent,
        parent_statement_id=None,
        lean_relative_path=f"statements/{statement_id_parent}.lean",
        latex_relative_path=f"statements/{statement_id_parent}.tex",
        is_resolved=False
    )

    init_db.add(parent_node)
    init_db.commit()

    # Create child node (resolving the parent node)
    child_node = GraphNode(
        project_id=project.id,
        title="Child Node",
        node_type="lemma",
        statement_id=statement_id_child,
        parent_statement_id=statement_id_parent,  # Linking to parent node
        lean_relative_path=f"statements/{statement_id_child}.lean",
        latex_relative_path=f"statements/{statement_id_child}.tex",
        is_resolved=True,
        proven_by_statement_id=statement_id_child  # Proven by itself
    )

    init_db.add(child_node)
    init_db.commit()

    # Fetch child node and assert that it's resolved
    child_node = GraphNode.query.filter_by(statement_id=statement_id_child).first()
    assert child_node.is_resolved is True
    assert child_node.proven_by_statement_id == statement_id_child