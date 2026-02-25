import pytest


def test_proposed_node_requires_valid_project(init_db):
    import uuid
    from app.models.proposed_node import ProposedNode

    proposal = ProposedNode(
        project_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Invalid Proposal",
        node_type="lemma",
        parent_statement_id=uuid.uuid4(),
        branch_name="user/x",
        lean_file_path="statements/x.lean"
    )

    init_db.add(proposal)

    with pytest.raises(Exception):
        init_db.commit()


def test_proposed_node_lifecycle(init_db):
    import uuid
    from app.models.project import Project
    from app.models.proposed_node import ProposedNode

    project = Project(
        name="PR Lifecycle",
        description="Testing status",
        leader_id=uuid.uuid4()
    )
    init_db.add(project)
    init_db.commit()

    proposal = ProposedNode(
        project_id=project.id,
        user_id=uuid.uuid4(),
        title="Lemma Proposal",
        node_type="lemma",
        parent_statement_id=uuid.uuid4(),
        branch_name="user/prop1",
        lean_file_path="statements/prop.lean",
        status="draft"
    )

    init_db.add(proposal)
    init_db.commit()

    # Simulate verification success
    proposal.status = "valid_sorry"
    proposal.github_pr_number = 42
    proposal.commit_sha = "abc123"
    init_db.commit()

    saved = ProposedNode.query.get(proposal.id)

    assert saved.status == "valid_sorry"
    assert saved.github_pr_number == 42