import os
import re

class LeanService:
    """Static helper methods for Lean source processing and import-tree utilities."""

    @staticmethod
    def module_to_relpath(module_name):
        """Convert a Lean module path into a relative `.lean` file path."""
        module_name = module_name.strip()
        if not module_name:
            return None

        parts = [part.strip() for part in module_name.split('.') if part.strip()]
        cleaned_parts = []
        for part in parts:
            if part.startswith('«') and part.endswith('»'):
                part = part[1:-1]
            cleaned_parts.append(part)

        if not cleaned_parts:
            return None

        return '/'.join(cleaned_parts) + '.lean'

    @staticmethod
    def parse_import_modules(lean_content):
        """Parse imported modules from Lean source content."""
        modules = []
        for raw_line in lean_content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('--'):
                continue
            if not line.startswith('import '):
                continue

            trailing = line[len('import '):].strip()
            if not trailing:
                continue
            modules.extend([part for part in trailing.split() if part])
        return modules

    @staticmethod
    def resolve_import_tree(entry_file, file_map):
        """Resolve all reachable Lean files from an entry file using import statements."""
        visited = set()
        stack = [entry_file]
        parent_map = {entry_file: None}

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            content = file_map.get(current)
            if content is None:
                continue

            for module in LeanService.parse_import_modules(content):
                rel_path = LeanService.module_to_relpath(module)
                if rel_path and rel_path in file_map and rel_path not in visited:
                    if rel_path not in parent_map:
                        parent_map[rel_path] = current
                    stack.append(rel_path)

        return visited, parent_map

    @staticmethod
    def build_path_to_file(target_file, parent_map):
        """Build the path chain from entry node to target file using parent map."""
        if target_file not in parent_map:
            return [target_file]

        path = []
        current = target_file
        while current is not None:
            path.append(current)
            current = parent_map.get(current)

        path.reverse()
        return path

    @staticmethod
    def build_sorry_traces(entry_file, sorry_locations, parent_map):
        """Build import traces for each discovered `sorry` occurrence."""
        traces = []
        for location in sorry_locations:
            target_file = location.get("file")
            path = LeanService.build_path_to_file(target_file, parent_map)
            traces.append({
                "file": target_file,
                "line": location.get("line"),
                "snippet": location.get("snippet", ""),
                "import_trace": path,
                "depth": max(0, len(path) - 1),
                "starts_at_entry": len(path) > 0 and path[0] == entry_file,
            })
        return traces

    @staticmethod
    def collect_sorry_locations(file_map):
        """Collect all lines containing `sorry` from a Lean file map."""
        locations = []
        for rel_path, content in file_map.items():
            for line_no, line in enumerate(content.splitlines(), start=1):
                if re.search(r'\bsorry\b', line):
                    locations.append({
                        "file": rel_path,
                        "line": line_no,
                        "snippet": line.strip(),
                    })
        return locations

    @staticmethod
    def collect_lean_files(worktree_root):
        """Load every Lean file in a worktree into a path-to-content map."""
        file_map = {}
        for root, _, files in os.walk(worktree_root):
            for file_name in files:
                if not file_name.endswith('.lean'):
                    continue
                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, worktree_root).replace('\\\\', '/')
                with open(full_path, 'r', encoding='utf-8') as file_handle:
                    file_map[rel_path] = file_handle.read()
        return file_map

    @staticmethod
    def write_text_file(worktree_root, rel_path, content):
        """Write UTF-8 text content at a worktree-relative path."""
        full_path = os.path.join(worktree_root, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as file_handle:
            file_handle.write(content)

    @staticmethod
    def extract_lemma_blocks(lean_code):
        """Extract theorem/lemma `:= by` blocks from Lean source text."""
        pattern = re.compile(
            r'(^\s*(?:lemma|theorem)\s+([A-Za-z_][A-Za-z0-9_\']*)[\s\S]*?:=\s*by[\s\S]*?(?=^\s*(?:theorem|lemma|def|example)\s+[A-Za-z_]|\Z))',
            re.MULTILINE,
        )
        matches = pattern.findall(lean_code)
        blocks = []
        for raw_block, lemma_name in matches:
            blocks.append({
                'name': lemma_name,
                'content': raw_block.strip(),
            })
        return blocks

    @staticmethod
    def build_split_main_content(lean_code, lemma_blocks):
        """Build updated main Lean content after extracting lemma blocks."""
        updated_main = lean_code
        import_lines = []

        for lemma in lemma_blocks:
            updated_main = updated_main.replace(lemma['content'], '')
            folder_segment = LeanService.to_node_folder_segment(lemma['name'])
            lemma_rel_main = f"{folder_segment}/main.lean"
            module_name = LeanService.lean_module_from_path(lemma_rel_main)
            import_lines.append(f"import {module_name}")

        import_header = '\n'.join(import_lines)
        return LeanService.normalize_lean_imports(f"{import_header}\n\n{updated_main.strip()}\n")

    @staticmethod
    def build_split_files(lemma_blocks):
        """Generate Lean and TeX files for split child lemmas."""
        lean_files = {}
        tex_files = {}
        lemma_names = []
        used_folder_names = set()

        for lemma in lemma_blocks:
            lemma_name = lemma['name']
            lemma_names.append(lemma_name)
            normalized_decl = LeanService.normalize_lemma_to_theorem(lemma['content'])
            folder_segment = LeanService.to_unique_node_folder_segment(lemma_name, used_folder_names)
            lemma_main_path = f"{folder_segment}/main.lean"
            lemma_tex_path = f"{folder_segment}/main.tex"

            lean_files[lemma_main_path] = f"import Definitions\n\n{normalized_decl}\n"
            tex_files[lemma_tex_path] = (
                "\\begin{theorem}[" + lemma_name + "]\n"
                "Auto-generated lemma extracted from split operation.\n"
                "\\end{theorem}\n\n"
                "\\begin{proof}\n"
                "By \\texttt{sorry}.\n"
                "\\end{proof}\n"
            )

        return lean_files, tex_files, lemma_names

    @staticmethod
    def normalize_lean_imports(lean_code):
        """Normalize variations of definitions imports to `import Definitions`."""
        normalized = re.sub(
            r'(?m)^\s*import\s+(?:Def|def|«def»|Definitions|definitions|«definitions»)\s*$',
            'import Definitions',
            lean_code,
        )
        return normalized

    @staticmethod
    def lean_text_equivalent(existing_code, new_code):
        """Compare Lean snippets after newline normalization and trim."""
        left = (existing_code or '').replace('\r\n', '\n').strip()
        right = (new_code or '').replace('\r\n', '\n').strip()
        return left == right

    @staticmethod
    def definition_file_paths(file_map):
        """Return known definitions file paths present in the provided file map."""
        candidates = ['Definitions.lean']
        return [path for path in candidates if path in file_map]

    @staticmethod
    def build_split_verification_payload(def_content, split_lean_code, project_goal=None):
        """Build compiler payload for split operation verification."""
        cleaned_split = re.sub(r'(?m)^\s*import\s+\S+\s*$', '', split_lean_code).strip()
        cleaned_split = LeanService.normalize_lemma_to_theorem(cleaned_split)
        def_block = def_content.strip()

        if def_block:
            return f"{def_block}\n\n{cleaned_split}\n"

        expanded_split = LeanService.expand_goaldef_in_split_code(cleaned_split, project_goal)
        if expanded_split is not None:
            return expanded_split

        return cleaned_split

    @staticmethod
    def build_verify_payload_from_reachable_map(reachable_map, entry_file, parent_map, project_goal=None):
        """Build compiler payload from the transitive import closure of an entry file."""
        definitions_content = LeanService.extract_definitions_content(reachable_map)
        if not definitions_content:
            definitions_content = LeanService.build_goaldef_from_project_goal(project_goal)

        sections = []
        if definitions_content.strip():
            sections.append(definitions_content.strip())

        non_definition_files = [
            path for path in reachable_map.keys()
            if path not in {'Definitions.lean', 'definitions.lean', 'def.lean', 'Def.lean'}
        ]
        ordered_files = sorted(
            non_definition_files,
            key=lambda path: (-LeanService.import_depth(path, parent_map), path == entry_file, path),
        )

        for rel_path in ordered_files:
            cleaned = re.sub(r'(?m)^\s*import\s+\S+\s*$', '', reachable_map.get(rel_path, '')).strip()
            if cleaned:
                sections.append(cleaned)

        return "\n\n".join(section for section in sections if section).strip() + "\n"

    @staticmethod
    def import_depth(target_file, parent_map):
        """Compute import depth of a file based on parent relationships."""
        depth = 0
        current = target_file
        seen = set()

        while current in parent_map and parent_map[current] is not None:
            parent = parent_map[current]
            if parent in seen:
                break
            seen.add(parent)
            depth += 1
            current = parent

        return depth

    @staticmethod
    def extract_definitions_content(file_map):
        """Extract and normalize the first recognized definitions file content."""
        for path in ('Definitions.lean', 'definitions.lean', 'def.lean', 'Def.lean'):
            if path in file_map:
                return LeanService.normalize_goaldef_file_content(file_map[path])
        return ''

    @staticmethod
    def build_goaldef_context_from_project(project):
        """Build GoalDef context from project imports, definitions, and goal expression."""
        raw_imports = getattr(project, 'goal_imports', None) or []
        normalized_imports = []

        for value in raw_imports:
            if not isinstance(value, str):
                continue
            entry = value.strip()
            if not entry:
                continue
            if entry.startswith('import '):
                entry = entry[7:].strip()
            if entry and entry not in normalized_imports:
                normalized_imports.append(entry)

        goal_definitions = (getattr(project, 'goal_definitions', None) or '').strip()
        return LeanService.build_goaldef_from_project_goal(
            project.goal,
            goal_imports=normalized_imports,
            goal_definitions=goal_definitions,
        )

    @staticmethod
    def normalize_lemma_to_theorem(code):
        """Normalize top-level `lemma` declarations into `theorem`."""
        return re.sub(r'(?m)^(\s*)lemma(\s+)', r'\1theorem\2', code)

    @staticmethod
    def expand_goaldef_in_split_code(split_code, project_goal):
        """Expand `GoalDef` theorem signatures using project goal binder information."""
        if ': GoalDef' not in split_code:
            return None

        binder = LeanService.extract_goal_binder(project_goal)
        if binder is None:
            return None

        name, typ, proposition = binder
        rewritten = re.sub(
            r"theorem\s+root\s*:\s*GoalDef\s*:=\s*by",
            f"theorem root ({name} : {typ}) : {proposition} := by",
            split_code,
            count=1,
        )

        rewritten = re.sub(
            rf"(?m)^\s*intro\s+{re.escape(name)}\s*$\n?",
            "",
            rewritten,
            count=1,
        )

        return rewritten.strip() + "\n"

    @staticmethod
    def extract_goal_binder(project_goal):
        """Extract `(name, type, proposition)` binder tuple from GoalDef expression."""
        expr = LeanService.normalize_goal_expression((project_goal or '').strip())

        match = re.match(r"^∀\s*\(([^:]+):\s*([^\)]+)\),\s*(.+)$", expr, re.DOTALL)
        if match:
            return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()

        match = re.match(r"^([A-Za-z_][A-Za-z0-9_']*)\s*:\s*([^,]+),\s*(.+)$", expr, re.DOTALL)
        if match:
            return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()

        return None

    @staticmethod
    def build_goaldef_from_project_goal(project_goal, goal_imports=None, goal_definitions=None):
        """Create a self-contained context block from project goal metadata."""
        goal_expr = LeanService.normalize_goal_expression((project_goal or '').strip())
        if not goal_expr:
            return ""

        imports = goal_imports or []
        definitions = (goal_definitions or '').strip()
        sections = []

        if imports:
            sections.extend([f"import {module}" for module in imports])
            sections.append("")

        sections.append("-- Generated from project goal")

        if definitions:
            sections.append(definitions.rstrip())
            sections.append("")

        return "\n".join(sections).rstrip() + "\n"

    @staticmethod
    def normalize_goaldef_file_content(content):
        """Normalize GoalDef declaration syntax from existing definitions file content."""
        text = content.strip()
        goaldef_pattern = re.compile(
            r"(?m)^(def|abbrev)\s+GoalDef\s*(?::\s*Prop\s*)?:=\s*(.*)$",
            re.DOTALL,
        )

        match = goaldef_pattern.search(text)
        if not match:
            return content

        decl_keyword = match.group(1)
        goal_expr = match.group(2).strip()
        if not goal_expr:
            return content

        normalized_goal_expr = LeanService.normalize_goal_expression(goal_expr)
        prefix = text[:match.start()].rstrip()
        goaldef_line = f"{decl_keyword} GoalDef := {normalized_goal_expr}"

        if prefix:
            return f"{prefix}\n\n{goaldef_line}\n"
        return goaldef_line + "\n"

    @staticmethod
    def normalize_goal_expression(goal_expr):
        """Normalize equivalent goal expression syntaxes into canonical Lean form."""
        expr = goal_expr.strip()

        full_decl_match = re.search(
            r"(?:def|abbrev)\s+GoalDef\s*(?::\s*Prop\s*)?:=\s*(.*)",
            expr,
            re.DOTALL,
        )
        if full_decl_match:
            expr = full_decl_match.group(1).strip()

        by_exact_decl_match = re.search(
            r"by\s*exact\s*\((.*)\)",
            expr,
            re.DOTALL,
        )
        if by_exact_decl_match:
            expr = by_exact_decl_match.group(1).strip()

        expr = re.sub(r"^--.*$", "", expr, flags=re.MULTILINE).strip()

        exact_match = re.match(r"^exact\s*\((.*)\)$", expr, re.DOTALL)
        if exact_match:
            expr = exact_match.group(1).strip()

        if expr.startswith('(') and expr.endswith(')'):
            inner = expr[1:-1].strip()
            if inner:
                expr = inner

        if expr.startswith('∀'):
            expr = LeanService.canonicalize_forall_binders(expr)
            return expr
        if expr.lower().startswith('forall '):
            expr = '∀ ' + expr[7:].strip()
            expr = LeanService.canonicalize_forall_binders(expr)
            return expr
        if re.match(r"^[A-Za-z_][A-Za-z0-9_']*\s*:\s*[^,]+,\s*.+$", expr):
            expr = f"∀ {expr}"
            expr = LeanService.canonicalize_forall_binders(expr)
            return expr
        return expr

    @staticmethod
    def canonicalize_forall_binders(expr):
        """Convert `∀ n : Nat, ...` into `∀ (n : Nat), ...` form."""
        match = re.match(r"^∀\s*([A-Za-z_][A-Za-z0-9_']*)\s*:\s*([^,]+),\s*(.+)$", expr, re.DOTALL)
        if not match:
            return expr

        name = match.group(1).strip()
        typ = match.group(2).strip()
        rest = match.group(3).strip()
        return f"∀ ({name} : {typ}), {rest}"

    @staticmethod
    def normalize_file_map_for_def_module(file_map):
        """Normalize imports in all files and normalize GoalDef content in Definitions."""
        normalized = {}
        for rel_path, content in file_map.items():
            normalized[rel_path] = LeanService.normalize_lean_imports(content)

        definitions_content = normalized.get('Definitions.lean')

        if definitions_content is not None:
            normalized['Definitions.lean'] = LeanService.normalize_goaldef_file_content(definitions_content)

        return normalized

    @staticmethod
    def lean_module_from_path(rel_lean_path):
        """Convert a relative Lean path into a Lean module name."""
        path_no_ext = rel_lean_path[:-5] if rel_lean_path.endswith('.lean') else rel_lean_path
        parts = [part for part in path_no_ext.replace('\\\\', '/').split('/') if part]

        module_parts = []
        for part in parts:
            if re.match(r'^[A-Z][A-Za-z0-9_]*$', part):
                module_parts.append(part)
            else:
                module_parts.append(f"«{part}»")

        return '.'.join(module_parts)

    @staticmethod
    def to_node_folder_segment(name):
        """Normalize a theorem name into a safe folder segment."""
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
        if not cleaned:
            cleaned = "Node"
        cleaned = cleaned.lower()
        if cleaned[0].isdigit():
            cleaned = f"node_{cleaned}"
        return cleaned

    @staticmethod
    def to_unique_node_folder_segment(name, used_folder_names):
        """Generate a unique folder segment for sibling nodes."""
        base = LeanService.to_node_folder_segment(name)
        candidate = base
        counter = 2
        while candidate in used_folder_names:
            candidate = f"{base}{counter}"
            counter += 1
        used_folder_names.add(candidate)
        return candidate

    @staticmethod
    def append_updated_node(updates, node):
        """Append or update one node entry in a node state update payload."""
        node_id = str(node.id)
        for entry in updates["updated_nodes"]:
            if entry.get("id") == node_id:
                entry["name"] = node.name
                entry["state"] = node.state
                return

        updates["updated_nodes"].append({
            "id": node_id,
            "name": node.name,
            "state": node.state,
        })

    @staticmethod
    def propagate_parent_states(parent_node, updates, node_model):
        """Propagate parent state from direct children using the provided node model."""
        current = parent_node
        while current is not None:
            children = node_model.query.filter_by(
                project_id=current.project_id,
                parent_node_id=current.id,
            ).all()

            if not children:
                current = current.parent
                continue

            expected_state = 'validated' if all(child.state == 'validated' for child in children) else 'sorry'
            if current.state != expected_state:
                current.state = expected_state
                LeanService.append_updated_node(updates, current)

            current = current.parent
