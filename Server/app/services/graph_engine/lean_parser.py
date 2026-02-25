# app/services/graph_engine/lean_parser.py

import re
import os
import uuid
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LeanParser:
    """
    Parses 'Statement-Centric' Lean files.
    Robustness Strategy:
    1. Prefer Headers.
    2. Fallback to Filename for ID.
    3. Default to 'root' for parent.
    """
    
    # Metadata Headers (Allow flexible spacing)
    STATEMENT_ID_REGEX = re.compile(r'^--\s*statement_id:\s*([a-f0-9\-]+)', re.MULTILINE)
    PARENT_ID_REGEX = re.compile(r'^--\s*parent_statement_id:\s*([a-f0-9\-]+|root)', re.MULTILINE)
    
    # Structure (theorem/lemma/etc)
    THEOREM_REGEX = re.compile(r'^\s*(theorem|lemma|def|corollary|axiom|example)\s+([a-zA-Z0-9_]+)', re.MULTILINE)
    
    # Dependencies: Matches 'import ...S_<uuid>' allowing for package variations
    # Captures the UUID part from the module name (S_uuid_with_underscores)
    IMPORT_REGEX = re.compile(r'^\s*import\s+.*\.S_([a-f0-9_]+)', re.MULTILINE)
    
    # Content Check
    SORRY_REGEX = re.compile(r'\bsorry\b')

    @staticmethod
    def _extract_uuid_from_filename(file_path: str) -> str | None:
        """
        Derives UUID from 'statements/S_<uuid_underscores>.lean'
        """
        basename = os.path.basename(file_path)
        # Remove extension
        name_no_ext = os.path.splitext(basename)[0]
        # Check prefix
        if name_no_ext.startswith("S_"):
            raw = name_no_ext[2:] # Strip S_
            # Convert underscores back to dashes
            return raw.replace("_", "-")
        return None

    @staticmethod
    def parse_file_content(content: str, file_path: str) -> Dict[str, Any]:
        """
        Extracts metadata, structure, and dependencies.
        Guarantees keys in return dict.
        """
        # 1. Statement ID Resolution
        stmt_match = LeanParser.STATEMENT_ID_REGEX.search(content)
        statement_id = stmt_match.group(1) if stmt_match else None
        
        if not statement_id:
            # Fallback: Infer from filename
            inferred = LeanParser._extract_uuid_from_filename(file_path)
            if inferred:
                try:
                    uuid.UUID(inferred)
                    statement_id = inferred
                    logger.warning(f"File {file_path} missing statement_id header. Inferred {statement_id} from filename.")
                except ValueError:
                    pass

        # 2. Parent Resolution
        parent_match = LeanParser.PARENT_ID_REGEX.search(content)
        parent_statement_id = parent_match.group(1) if parent_match else 'root'
        if parent_statement_id == 'root':
            parent_statement_id = None

        # 3. Dependencies (DAG Edges)
        dependencies = []
        for match in LeanParser.IMPORT_REGEX.finditer(content):
            raw_uuid = match.group(1)
            # Normalize to standard UUID format
            formatted_uuid = raw_uuid.replace('_', '-')
            dependencies.append(formatted_uuid)

        # 4. Definition Analysis
        node_type = "lemma"
        title = "unknown"
        def_match = LeanParser.THEOREM_REGEX.search(content)
        if def_match:
            node_type = def_match.group(1)
            title = def_match.group(2)
            
        # 5. Local "Texual" Resolution Status
        has_sorry = bool(LeanParser.SORRY_REGEX.search(content))

        return {
            "statement_id": statement_id,
            "parent_statement_id": parent_statement_id,
            "title": title,
            "node_type": node_type,
            "dependencies": dependencies, # List of UUID strings
            "has_sorry": has_sorry,
            "parse_error": False if statement_id else True
        }