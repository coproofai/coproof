import hashlib
import json
import re
import gzip
import base64
from io import StringIO
import csv
from pathlib import PurePosixPath

from app.exceptions import CoProofError
from app.services.lean_service import LeanService


class ComputationService:
    """Helpers for computation node request validation and artifact generation."""

    SUPPORTED_LANGUAGES = {'python', 'mpi'}
    DEFAULT_TIMEOUT_SECONDS = 120

    @staticmethod
    def ensure_proof_node(node):
        if node.node_kind != 'proof':
            raise CoProofError('This operation is only valid for proof nodes.', code=400)

    @staticmethod
    def ensure_computation_node(node):
        if node.node_kind != 'computation':
            raise CoProofError('This operation is only valid for computation nodes.', code=400)

    @staticmethod
    def build_computation_child_name(parent_name):
        base = (parent_name or '').strip()
        if not base:
            return 'computation_node'
        if base.endswith('_computation'):
            return base
        return f'{base}_computation'

    @staticmethod
    def render_lean_declaration(keyword, name, signature):
        normalized_signature = (signature or '').strip()
        if not normalized_signature:
            raise CoProofError('Lean declaration signature cannot be empty.', code=400)

        # Signatures extracted from source already include the leading ': type'
        # so we only add ': ' ourselves when there is no leading colon or binder.
        # NOTE: '{' that starts a set-builder expression like {n : ℕ | ...} must NOT
        # be treated as an implicit binder — only treat '{' as a binder prefix when
        # it does NOT contain a pipe ('|'), which is the set-builder separator.
        is_binder_prefix = normalized_signature.startswith(('(', '[', ':')) or (
            normalized_signature.startswith('{') and ' | ' not in normalized_signature
        )
        if is_binder_prefix:
            return f'{keyword} {name} {normalized_signature}'

        return f'{keyword} {name} : {normalized_signature}'

    @staticmethod
    def extract_theorem_signature_from_lean(lean_code, theorem_name):
        if not lean_code or not theorem_name:
            return None

        match = re.search(rf'(?m)^\s*(?:theorem|lemma)\s+{re.escape(theorem_name)}\b', lean_code)
        if not match:
            return None

        tail = lean_code[match.end():]
        depth_paren = 0
        depth_brace = 0
        depth_bracket = 0
        end_index = None

        for index, char in enumerate(tail[:-1]):
            if char == '(':
                depth_paren += 1
            elif char == ')':
                depth_paren = max(0, depth_paren - 1)
            elif char == '{':
                depth_brace += 1
            elif char == '}':
                depth_brace = max(0, depth_brace - 1)
            elif char == '[':
                depth_bracket += 1
            elif char == ']':
                depth_bracket = max(0, depth_bracket - 1)

            if depth_paren == 0 and depth_brace == 0 and depth_bracket == 0 and tail[index:index + 2] == ':=':
                end_index = index
                break

        if end_index is None:
            return None

        signature = tail[:end_index].strip()
        if not signature or ':' not in signature:
            return None

        explicit_binder_names = []
        binder_prefix_match = re.match(r'^(?P<prefix>(?:\s*(?:\([^)]*\)|\{[^}]*\}|\[[^]]*\]))*)', signature, re.DOTALL)
        binder_prefix = binder_prefix_match.group('prefix') if binder_prefix_match else ''

        for binder_content in re.findall(r'\(([^()]*)\)', binder_prefix):
            if ':' not in binder_content:
                continue
            names_part = binder_content.split(':', 1)[0].strip()
            for candidate in names_part.split():
                if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_\']*', candidate):
                    explicit_binder_names.append(candidate)

        return {
            'signature': signature,
            'explicit_binder_names': explicit_binder_names,
        }

    @staticmethod
    def normalize_execution_request(payload):
        payload = payload or {}

        language = (payload.get('language') or 'python').strip().lower()
        if language not in ComputationService.SUPPORTED_LANGUAGES:
            supported = ', '.join(sorted(ComputationService.SUPPORTED_LANGUAGES))
            raise CoProofError(f'Unsupported computation language. Supported values: {supported}', code=400)

        source_code = payload.get('source_code') or payload.get('code')
        if not isinstance(source_code, str) or not source_code.strip():
            raise CoProofError('Missing payload: code', code=400)

        entrypoint = (payload.get('entrypoint') or 'run').strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', entrypoint):
            raise CoProofError('entrypoint must be a valid Python identifier.', code=400)

        target = payload.get('target')
        if not isinstance(target, dict) or not target:
            raise CoProofError('target must be a non-empty object.', code=400)

        lean_statement = payload.get('lean_statement')
        if not isinstance(lean_statement, str) or not lean_statement.strip():
            raise CoProofError('lean_statement is required for computation nodes.', code=400)

        timeout_seconds = payload.get('timeout_seconds') or ComputationService.DEFAULT_TIMEOUT_SECONDS
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            raise CoProofError('timeout_seconds must be an integer.', code=400)

        if timeout_seconds <= 0 or timeout_seconds > 900:
            raise CoProofError('timeout_seconds must be between 1 and 900.', code=400)

        return {
            'language': language,
            'source_code': source_code.rstrip() + '\n',
            'entrypoint': entrypoint,
            'input_data': payload.get('input_data'),
            'target': target,
            'lean_statement': lean_statement.strip(),
            'timeout_seconds': timeout_seconds,
        }

    @staticmethod
    def build_persisted_spec(request_data):
        return {
            'language': request_data['language'],
            'entrypoint': request_data['entrypoint'],
            'target': request_data['target'],
            'lean_statement': request_data['lean_statement'],
            'timeout_seconds': request_data['timeout_seconds'],
        }

    @staticmethod
    def summarize_computation_result(computation_result):
        records = computation_result.get('records')
        records_count = len(records) if isinstance(records, list) else 0
        evidence = computation_result.get('evidence')
        evidence_preview = evidence

        if isinstance(evidence, dict):
            preview = {}
            for key, value in evidence.items():
                if isinstance(value, (dict, list)):
                    preview[key] = '<omitted>'
                elif isinstance(value, str) and len(value) > 500:
                    preview[key] = value[:500] + '...'
                else:
                    preview[key] = value
            evidence_preview = preview

        return {
            'completed': bool(computation_result.get('completed', False)),
            'sufficient': bool(computation_result.get('sufficient', False)),
            'summary': computation_result.get('summary'),
            'error': computation_result.get('error'),
            'processing_time_seconds': computation_result.get('processing_time_seconds'),
            'roundtrip_time_seconds': computation_result.get('roundtrip_time_seconds'),
            'timing_source': computation_result.get('timing_source'),
            'records_count': records_count,
            'evidence_preview': evidence_preview,
            'rank_hosts': computation_result.get('rank_hosts'),
        }

    @staticmethod
    def sanitize_lean_identifier(value):
        cleaned = re.sub(r'[^A-Za-z0-9_]', '_', (value or '').strip())
        cleaned = re.sub(r'_+', '_', cleaned).strip('_') or 'computation_result'
        if cleaned[0].isdigit():
            cleaned = f'node_{cleaned}'
        return cleaned

    @staticmethod
    def build_computation_child_artifacts(child_name, folder_segment, parent_theorem_signature='GoalDef'):
        theorem_name = ComputationService.sanitize_lean_identifier(child_name)
        child_main_path = f"{folder_segment}/main.lean"
        child_tex_path = f"{folder_segment}/main.tex"
        child_program_path = f"{folder_segment}/computation.py"
        theorem_declaration = ComputationService.render_lean_declaration(
            'theorem',
            theorem_name,
            parent_theorem_signature,
        )

        child_main_content = (
            "import Definitions\n\n"
            f"{theorem_declaration} := by\n"
            "  sorry\n"
        )
        child_tex_content = (
            "\\begin{theorem}[Computation Node]\\n"
            f"{child_name}\\n"
            "\\end{theorem}\\n\\n"
            "\\begin{proof}\\n"
            "Pending computational evidence.\\n"
            "\\end{proof}\\n"
        )
        child_program_template = (
            "def run(input_data, target):\n"
            "    return {\n"
            "        \"evidence\": {\n"
            "            \"input_data\": input_data,\n"
            "            \"target\": target\n"
            "        },\n"
            "        \"sufficient\": False,\n"
            "        \"summary\": \"Replace this template with a real computation\",\n"
            "        \"records\": []\n"
            "    }\n"
        )

        return {
            "theorem_name": theorem_name,
            "child_main_path": child_main_path,
            "child_tex_path": child_tex_path,
            "child_program_path": child_program_path,
            "child_main_content": child_main_content,
            "child_tex_content": child_tex_content,
            "child_program_template": child_program_template,
        }

    @staticmethod
    def inject_child_import_and_usage(parent_main_content, child_main_path, child_theorem_name, explicit_binder_names=None):
        module_name = LeanService.lean_module_from_path(child_main_path)
        import_line = f"import {module_name}"

        updated = parent_main_content or ''
        if import_line not in updated:
            updated = f"{import_line}\n" + updated

        explicit_binder_names = explicit_binder_names or []
        binder_suffix = ''.join(f' {name}' for name in explicit_binder_names)
        replacement = f'  simpa using {child_theorem_name}{binder_suffix}'

        updated, replaced = re.subn(r'(?m)^\s*sorry\s*$', replacement, updated, count=1)
        if replaced == 0:
            updated = updated.rstrip() + f"\n\n-- TODO: incorporate computation node {child_theorem_name}{binder_suffix} into this proof.\n"

        return LeanService.normalize_lean_imports(updated)

    @staticmethod
    def build_evidence_document(node_name, request_data, computation_result):
        records = computation_result.get('records')
        records_count = len(records) if isinstance(records, list) else 0
        return {
            'node_name': node_name,
            'language': request_data['language'],
            'entrypoint': request_data['entrypoint'],
            'target': request_data['target'],
            'lean_statement': request_data['lean_statement'],
            'sufficient': bool(computation_result.get('sufficient', False)),
            'evidence': computation_result.get('evidence'),
            'summary': computation_result.get('summary'),
            'records_count': records_count,
            'stdout': computation_result.get('stdout', ''),
            'stderr': computation_result.get('stderr', ''),
            'error': computation_result.get('error'),
            'processing_time_seconds': computation_result.get('processing_time_seconds'),
        }

    @staticmethod
    def _gzip_b64_from_text(text):
        compressed = gzip.compress(text.encode('utf-8'))
        return base64.b64encode(compressed).decode('ascii')

    @staticmethod
    def _records_to_csv(records):
        if not isinstance(records, list) or not records:
            return ""

        normalized = [item for item in records if isinstance(item, dict)]
        if not normalized:
            return ""

        headers = sorted({key for item in normalized for key in item.keys()})
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        for item in normalized:
            row = {}
            for key in headers:
                value = item.get(key)
                if isinstance(value, (dict, list)):
                    row[key] = json.dumps(value, ensure_ascii=True, sort_keys=True)
                else:
                    row[key] = value
            writer.writerow(row)
        return buffer.getvalue()

    @staticmethod
    def build_lean_artifact(node_name, request_data, evidence_doc, evidence_path, program_path):
        theorem_name = ComputationService.sanitize_lean_identifier(node_name)
        evidence_json = json.dumps(evidence_doc, sort_keys=True, ensure_ascii=True)
        evidence_hash = hashlib.sha256(evidence_json.encode('utf-8')).hexdigest()[:16]
        target_json = json.dumps(request_data['target'], sort_keys=True, ensure_ascii=True)
        axiom_declaration = ComputationService.render_lean_declaration(
            'axiom',
            theorem_name,
            request_data['lean_statement'],
        )

        return (
            'import Definitions\n\n'
            '/--\n'
            f'Computation-backed certificate for node `{node_name}`.\n'
            f'Program artifact: {program_path}\n'
            f'Evidence artifact: {evidence_path}\n'
            f'Evidence hash: {evidence_hash}\n'
            f'Target: {target_json}\n'
            '-/\n'
            f'{axiom_declaration}\n'
        )

    @staticmethod
    def build_tex_artifact(node_name, evidence_doc):
        summary = evidence_doc.get('summary') or 'Computation-backed evidence available in evidence.json.'
        safe_summary = str(summary).replace('\\', '\\textbackslash{}').replace('_', '\\_')
        return (
            '\\section*{Computation Evidence}\n'
            f'\\textbf{{Node}}: {node_name}\\\\\n'
            f'\\textbf{{Verdict}}: {"sufficient" if evidence_doc.get("sufficient") else "insufficient"}\\\\\n'
            f'\\textbf{{Summary}}: {safe_summary}\n'
        )

    @staticmethod
    def build_artifact_bundle(node_main_path, node_name, request_data, computation_result):
        main_path = PurePosixPath(node_main_path)
        folder = main_path.parent
        program_filename = 'computation.py' if request_data['language'] == 'python' else 'computation.txt'
        program_path = str(folder / program_filename)
        evidence_path = str(folder / 'evidence.json')
        evidence_full_compressed_path = str(folder / 'evidence_full.json.gz.b64')
        evidence_records_csv_compressed_path = str(folder / 'evidence_records.csv.gz.b64')
        tex_path = str(folder / 'main.tex')

        evidence_doc = ComputationService.build_evidence_document(node_name, request_data, computation_result)
        full_result_json = json.dumps(computation_result, indent=2, sort_keys=True, ensure_ascii=True) + '\n'
        records_csv = ComputationService._records_to_csv(computation_result.get('records'))
        records_csv_gz_b64 = ComputationService._gzip_b64_from_text(records_csv) if records_csv else ''
        full_result_gz_b64 = ComputationService._gzip_b64_from_text(full_result_json)

        evidence_doc['artifacts'] = {
            'full_result_compressed_b64': evidence_full_compressed_path,
            'records_csv_compressed_b64': evidence_records_csv_compressed_path if records_csv else None,
            'decompress_hint': (
                "Python: import gzip,base64,pathlib; raw=base64.b64decode(pathlib.Path('<file>.gz.b64').read_text()); "
                "print(gzip.decompress(raw).decode('utf-8')[:500])"
            ),
            'full_result_hash_sha256': hashlib.sha256(full_result_json.encode('utf-8')).hexdigest(),
            'records_csv_hash_sha256': hashlib.sha256(records_csv.encode('utf-8')).hexdigest() if records_csv else None,
        }

        bundle = {
            str(main_path): ComputationService.build_lean_artifact(
                node_name=node_name,
                request_data=request_data,
                evidence_doc=evidence_doc,
                evidence_path=evidence_path,
                program_path=program_path,
            ),
            program_path: request_data['source_code'],
            evidence_path: json.dumps(evidence_doc, indent=2, sort_keys=True, ensure_ascii=True) + '\n',
            evidence_full_compressed_path: full_result_gz_b64 + '\n',
            tex_path: ComputationService.build_tex_artifact(node_name, evidence_doc),
        }

        if records_csv_gz_b64:
            bundle[evidence_records_csv_compressed_path] = records_csv_gz_b64 + '\n'

        return bundle