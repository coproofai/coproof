import pytest
from app.services.git_engine.file_service import FileService

def test_path_generation():
    uid = "550e8400-e29b-41d4-a716-446655440000"
    paths = FileService.generate_paths(uid)
    expected_module = "S_550e8400_e29b_41d4_a716_446655440000"
    
    assert paths['lean'] == f"statements/{expected_module}.lean"
    assert paths['tex'] == f"statements/{expected_module}.tex"

def test_scaffold_generation():
    uid = "abc-123"
    parent_uid = "root"
    scaffold = FileService.generate_lean_scaffold(
        statement_id=uid,
        parent_statement_id=None,
        statement_type="theorem",
        statement_name="MyTheorem",
        statement_signature="1 + 1 = 2",
        proof_body="rfl"
    )
    
    assert f"-- statement_id: {uid}" in scaffold
    assert "-- parent_statement_id: root" in scaffold
    assert "theorem MyTheorem : 1 + 1 = 2 := by" in scaffold
    assert "  rfl" in scaffold

def test_main_file_imports(tmp_path):
    # Setup dummy worktree structure
    statements_dir = tmp_path / "statements"
    statements_dir.mkdir()
    
    uid1 = "111-aaa"
    uid2 = "222-bbb"
    
    mod1 = FileService._uuid_to_module_name(uid1)
    mod2 = FileService._uuid_to_module_name(uid2)
    
    (statements_dir / f"{mod1}.lean").touch()
    (statements_dir / f"{mod2}.lean").touch()
    
    # Generate Main
    main_path = FileService.generate_main_file(str(tmp_path), [uid1, uid2], "TestProj")
    
    with open(main_path, 'r') as f:
        content = f.read()
    
    assert f"import «TestProj».statements.{mod1}" in content
    assert f"import «TestProj».statements.{mod2}" in content