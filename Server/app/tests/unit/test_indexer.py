from unittest.mock import patch
from app.services.graph_engine.indexer import GraphIndexer
from app.models.graph_index import GraphNode
from app.models.project import Project
from app.models.user import User

def test_indexer_logic(init_db):
    # Setup Data
    u = User(full_name="U", email="u@i.com", password_hash="x")
    init_db.session.add(u)
    init_db.session.commit()
    
    p = Project(name="Index Proj", leader_id=u.id)
    init_db.session.add(p)
    init_db.session.commit()
    
    # Pre-existing dependency node
    dep_node = GraphNode(project_id=p.id, title="lemma_base", node_type="lemma", file_path="base.lean")
    init_db.session.add(dep_node)
    init_db.session.commit()
    
    # Content to parse
    # A theorem that depends on 'lemma_base'
    content = """
    /- COPROOF: DEPENDS [lemma_base] -/
    theorem new_result : ...
    """
    
    # Execute Indexer
    GraphIndexer.index_file_content(str(p.id), "src/new.lean", "abc123hash", content)
    
    # Verify Node Creation
    new_node = GraphNode.query.filter_by(title="new_result").first()
    assert new_node is not None
    assert new_node.node_type == "theorem"
    assert new_node.commit_hash == "abc123hash"
    
    # Verify Edge Creation
    assert new_node.prerequisites.count() == 1
    assert new_node.prerequisites.first().title == "lemma_base"