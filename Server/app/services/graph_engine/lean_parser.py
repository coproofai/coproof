import re

class LeanParser:
    """
    Parses Lean 4 files to extract structure.
    Expects CoProof metadata in comments.
    """
    
    # Regex to find: theorem name : type :=
    # Matches: "theorem pythagoras (a b : Nat) : ..."
    THEOREM_REGEX = re.compile(r'^\s*(theorem|lemma|def|corollary)\s+([a-zA-Z0-9_]+)', re.MULTILINE)
    
    # Regex to find metadata header
    # /- COPROOF: DEPENDS [lemma1, lemma2] -/
    DEPENDS_REGEX = re.compile(r'/-\s*COPROOF:\s*DEPENDS\s*\[(.*?)\]\s*-/')

    @staticmethod
    def parse_file_content(content: str):
        """
        Returns a list of node definitions found in the text.
        """
        results = []
        
        # 1. Find Dependencies (Global for the file for now, or per block)
        dependencies = []
        dep_match = LeanParser.DEPENDS_REGEX.search(content)
        if dep_match:
            # Parse list: "lemma1, lemma2" -> ["lemma1", "lemma2"]
            raw_deps = dep_match.group(1)
            dependencies = [d.strip() for d in raw_deps.split(',') if d.strip()]

        # 2. Find Definitions
        for match in LeanParser.THEOREM_REGEX.finditer(content):
            node_type = match.group(1) # theorem, lemma...
            name = match.group(2)      # pythagoras
            
            # Map lean keywords to DB Enums
            db_type = node_type
            if node_type == 'def':
                db_type = 'definition'
            
            results.append({
                "title": name,
                "node_type": db_type,
                "dependencies": dependencies, # Assign file-level deps to the node
                "line_number": content.count('\n', 0, match.start()) + 1
            })
            
        return results