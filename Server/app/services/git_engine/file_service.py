# app/services/graph_engine/file_service.py

import os
import re
import uuid
from app.exceptions import CoProofError, GitOperationError

class FileService:
    """
    Enforces the rigid file structure for the Statement-Centric architecture.
    Handles path generation, scaffold creation, and Main.lean composition.
    No Database access.
    """

    # Directory where immutable statements live
    STATEMENTS_DIR = "statements"
    
    @staticmethod
    def _validate_uuid(val: str, field_name: str):
        """
        Helper to ensure headers contain valid UUIDs.
        """
        if val == 'root': 
            return
        try:
            uuid.UUID(str(val))
        except ValueError:
            raise CoProofError(f"Invalid UUID for {field_name}: {val}")
    @staticmethod
    def _uuid_to_module_name(statement_id_str: str) -> str:
        """
        Converts a UUID to a valid Lean 4 module identifier.
        Lean identifiers cannot start with numbers or contain hyphens.
        Format: S_<uuid_with_underscores>
        """
        sanitized = statement_id_str.replace("-", "_")
        return f"S_{sanitized}"

    @staticmethod
    def generate_paths(statement_id: str):
        """
        Returns the enforced relative file paths for a statement.
        """
        module_name = FileService._uuid_to_module_name(str(statement_id))
        return {
            "lean": f"{FileService.STATEMENTS_DIR}/{module_name}.lean",
            "tex": f"{FileService.STATEMENTS_DIR}/{module_name}.tex"
        }

    @staticmethod
    def generate_lean_scaffold(
        statement_id: str,
        parent_statement_id: str | None,
        statement_type: str,
        statement_name: str,
        statement_signature: str,
        proof_body: str = "sorry",
        dependency_ids: list[str] = None # List of UUID strings
    ) -> str:
        """
        Generates rigid statement file content.
        Enforces UUID-based imports.
        """
        # 1. Validation
        FileService._validate_uuid(statement_id, "statement_id")
        if parent_statement_id:
            FileService._validate_uuid(parent_statement_id, "parent_statement_id")


        for dep_id in dependency_ids:
            FileService._validate_uuid(dep_id, f"dependency {dep_id}")


        # Validate inputs
        if not statement_name or not statement_name.isidentifier():
             # Basic sanity check, Lean has specific rules but this catches obvious issues
             raise CoProofError("Invalid statement name: Must be a valid identifier.")
        
        if not statement_signature.strip():
             raise CoProofError("Statement signature (type) cannot be empty.")

        # Header Construction
        # These headers are the Source of Truth for the Graph Indexer
        header = f"-- statement_id: {statement_id}\n"
        if parent_statement_id:
            header += f"-- parent_statement_id: {parent_statement_id}\n"
        else:
            header += f"-- parent_statement_id: root\n"

        # 3. Import Construction (UUID-based Resolution)
        imports = "import Mathlib\n" # Always include base
        if dependency_ids:
            for dep_id in dependency_ids:
                FileService._validate_uuid(dep_id, "dependency_id")
                mod_name = FileService._uuid_to_module_name(dep_id)
                # Assumes standard project structure
                imports += f"import «Project».{FileService.STATEMENTS_DIR}.{mod_name}\n"

        # 4. Content Construction
        scaffold = (
            f"{header}\n"
            f"{imports}\n"
            f"{statement_type} {statement_name} : {statement_signature} := by\n"
            f"  {proof_body}\n"
        )
        
        return scaffold

    @staticmethod
    def generate_main_file(worktree_path: str, ordered_statement_ids: list[str], project_name: str = "Project") -> str:
        """
        Generates Main.lean by importing statement files in topological order.
        
        Validates existence of all files BEFORE generating.
        Fails gracefully with a list of missing dependencies if the Git state is incomplete.
        """
        output_path = os.path.join(worktree_path, "Main.lean")
        missing_files = []
        import_lines = []

        # 1. Verification Loop
        for stmt_id in ordered_statement_ids:
            module_name = FileService._uuid_to_module_name(stmt_id)
            rel_path = f"{FileService.STATEMENTS_DIR}/{module_name}.lean"
            full_path = os.path.join(worktree_path, rel_path)
            
            if not os.path.exists(full_path):
                missing_files.append(f"{rel_path} (ID: {stmt_id})")
            else:
                # Prepare import line using standard Lean 4 syntax
                # import «Project».statements.S_uuid
                import_lines.append(f"import «{project_name}».{FileService.STATEMENTS_DIR}.{module_name}\n")

        # 2. Graceful Failure
        if missing_files:
            error_msg = f"Cannot generate Main.lean. The following dependencies are missing in the worktree: {', '.join(missing_files)}"
            raise GitOperationError(error_msg)

        # 3. Write File
        try:
            with open(output_path, 'w') as outfile:
                outfile.write(f"-- Auto-generated by CoProof\n")
                outfile.write(f"-- Source of Truth: Topological DAG\n\n")
                outfile.writelines(import_lines)
            
            return output_path

        except IOError as e:
            raise GitOperationError(f"Failed to write Main.lean: {e}")