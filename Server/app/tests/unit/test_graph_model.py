from app.models.user import User
from app.models.project import Project
from app.models.graph_index import GraphNode

def test_graph_dependencies(init_db):
    """Test that nodes can link to each other (Directed Graph)."""
    # Setup
    leader = User(full_name="Euler", email="e@math.com", password_hash="x")
    init_db.session.add(leader)
    init_db.session.commit()
    
    proj = Project(name="Graph Theory", leader_id=leader.id)
    init_db.session.add(proj)
    init_db.session.commit()
    
    # Nodes
    lemma = GraphNode(
        project_id=proj.id, title="Lemma 1", node_type="lemma",
        file_path="src/lemma.lean"
    )
    theorem = GraphNode(
        project_id=proj.id, title="Main Theorem", node_type="theorem",
        file_path="src/theorem.lean"
    )
    
    # Theorem depends on Lemma (Theorem -> Lemma)
    theorem.prerequisites.append(lemma)
    
    init_db.session.add_all([lemma, theorem])
    init_db.session.commit()
    
    # Verify
    assert theorem.prerequisites.count() == 1
    assert theorem.prerequisites.first().title == "Lemma 1"
    
    # Check reverse relationship
    assert lemma.dependents.count() == 1
    assert lemma.dependents.first().title == "Main Theorem"