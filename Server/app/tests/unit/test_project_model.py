from app.models.user import User
from app.models.project import Project

def test_project_relationships(init_db):
    """Test project leader and members."""
    leader = User(full_name="Leader", email="leader@test.com", password_hash="x")
    collab = User(full_name="Collab", email="collab@test.com", password_hash="x")
    init_db.session.add_all([leader, collab])
    init_db.session.commit()

    project = Project(
        name="CoProof Core",
        visibility="public",
        leader_id=leader.id,
        remote_repo_url="http://github.com/coproof/core.git"
    )
    project.members.append(collab)
    
    init_db.session.add(project)
    init_db.session.commit()

    assert project.leader.email == "leader@test.com"
    assert len(project.members) == 1
    assert project.members[0].email == "collab@test.com"