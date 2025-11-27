from app.services.graph_engine.lean_parser import LeanParser

def test_parse_simple_lean_file():
    content = """
    /- COPROOF: DEPENDS [lemma_basic, axiom_1] -/
    
    import Mathlib
    
    lemma helper_calc : 1 + 1 = 2 := by rfl
    
    theorem main_result (n : Nat) : n = n := by rfl
    """
    
    results = LeanParser.parse_file_content(content)
    
    assert len(results) == 2
    
    # Check Lemma
    lemma = results[0]
    assert lemma['title'] == 'helper_calc'
    assert lemma['node_type'] == 'lemma'
    assert 'lemma_basic' in lemma['dependencies']
    
    # Check Theorem
    theorem = results[1]
    assert theorem['title'] == 'main_result'
    assert theorem['node_type'] == 'theorem'