import hashlib
import re
import subprocess
import tempfile
import time
import os


def find_lean_executable():
    possible_commands = ["lean", "lean.exe"]

    for cmd in possible_commands:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    possible_paths = [
        os.path.expanduser("~/.elan/bin/lean"),
        os.path.expanduser("~/.elan/bin/lean.exe"),
        "/usr/local/elan/bin/lean",
        "/usr/local/elan/bin/lean.exe",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def parse_theorem_info(lean_code: str):
    theorems = []
    lines = lean_code.split("\n")
    theorem_pattern = re.compile(r"^\s*(theorem|def|lemma|example)\s+(\w+)")

    for index, line in enumerate(lines, 1):
        match = theorem_pattern.match(line)
        if match:
            theorem_type = match.group(1)
            theorem_name = match.group(2)
            theorems.append(
                {
                    "name": theorem_name,
                    "type": theorem_type,
                    "line": index,
                    "column": match.start(2) + 1,
                }
            )

    return theorems


def parse_lean_messages(stdout: str, stderr: str, filename: str = "proof.lean"):
    messages = []

    error_pattern = re.compile(
        r"([^:]+):(\d+):(\d+):\s*(error|warning|info):\s*(.*?)(?=\n[^\s]|\Z)",
        re.DOTALL,
    )

    combined_output = stderr + "\n" + stdout

    for match in error_pattern.finditer(combined_output):
        line = int(match.group(2))
        column = int(match.group(3))
        severity = match.group(4)
        message = match.group(5).strip()

        messages.append(
            {
                "file": filename,
                "line": line,
                "column": column,
                "severity": severity,
                "message": message,
            }
        )

    return messages


def verify_lean_proof(lean_code: str, filename: str = "proof.lean"):
    start_time = time.time()
    lean_executable = find_lean_executable()

    if not lean_executable:
        end_time = time.time()
        return {
            "verified": False,
            "returnCode": -1,
            "theorems": [],
            "messages": [
                {
                    "file": filename,
                    "line": 0,
                    "column": 0,
                    "severity": "error",
                    "message": "Lean executable not found. Please install Lean 4 via elan.",
                }
            ],
            "feedback": {
                "stdout": "",
                "stderr": "Lean executable not found. Please install Lean 4 via elan.",
            },
            "processingTimeSeconds": round(end_time - start_time, 3),
        }

    timestamp = str(time.time()).encode("utf-8")
    code_hash = hashlib.sha256(lean_code.encode("utf-8") + timestamp).hexdigest()[:16]
    base_filename = filename.rsplit(".", 1)[0] if "." in filename else filename
    hashed_filename = f"{base_filename}_{code_hash}.lean"

    with tempfile.TemporaryDirectory() as temp_dir:
        lean_file_path = os.path.join(temp_dir, hashed_filename)

        with open(lean_file_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(lean_code)

        try:
            result = subprocess.run(
                [lean_executable, lean_file_path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=temp_dir,
            )

            verified = result.returncode == 0
            end_time = time.time()

            all_messages = parse_lean_messages(result.stdout, result.stderr, hashed_filename)
            theorems = parse_theorem_info(lean_code)
            theorems_with_details = []

            for theorem in theorems:
                theorem_messages = [
                    msg for msg in all_messages if msg["line"] == theorem["line"]
                ]
                location = f"{hashed_filename}:{theorem['line']}:{theorem['column']}"
                theorems_with_details.append(
                    {
                        "name": theorem["name"],
                        "type": theorem["type"],
                        "location": location,
                        "line": theorem["line"],
                        "column": theorem["column"],
                        "messages": theorem_messages,
                    }
                )

            return {
                "verified": verified,
                "returnCode": result.returncode,
                "theorems": theorems_with_details,
                "messages": all_messages,
                "feedback": {
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                },
                "processingTimeSeconds": round(end_time - start_time, 3),
            }

        except subprocess.TimeoutExpired:
            end_time = time.time()
            return {
                "verified": False,
                "returnCode": -1,
                "theorems": [],
                "messages": [
                    {
                        "file": filename,
                        "line": 0,
                        "column": 0,
                        "severity": "error",
                        "message": "Verification timeout after 60 seconds",
                    }
                ],
                "feedback": {
                    "stdout": "",
                    "stderr": "Verification timeout after 60 seconds",
                },
                "processingTimeSeconds": round(end_time - start_time, 3),
            }
        except FileNotFoundError as error:
            end_time = time.time()
            return {
                "verified": False,
                "returnCode": -1,
                "theorems": [],
                "messages": [
                    {
                        "file": filename,
                        "line": 0,
                        "column": 0,
                        "severity": "error",
                        "message": f"Lean executable not found: {str(error)}",
                    }
                ],
                "feedback": {
                    "stdout": "",
                    "stderr": f"Lean executable not found: {str(error)}",
                },
                "processingTimeSeconds": round(end_time - start_time, 3),
            }
        except Exception as error:
            end_time = time.time()
            return {
                "verified": False,
                "returnCode": -1,
                "theorems": [],
                "messages": [
                    {
                        "file": filename,
                        "line": 0,
                        "column": 0,
                        "severity": "error",
                        "message": str(error),
                    }
                ],
                "feedback": {
                    "stdout": "",
                    "stderr": str(error),
                },
                "processingTimeSeconds": round(end_time - start_time, 3),
            }


def to_compiler_snippet_response(lean_code: str, filename: str = "snippet.lean"):
    result = verify_lean_proof(lean_code, filename)
    errors = [
        {
            "line": message.get("line", 0),
            "column": message.get("column", 0),
            "message": message.get("message", ""),
        }
        for message in result.get("messages", [])
        if message.get("severity") == "error"
    ]

    return {
        "valid": result.get("verified", False),
        "errors": errors,
        "processing_time_seconds": result.get("processingTimeSeconds", 0.0),
        "return_code": result.get("returnCode", -1),
        "message_count": len(result.get("messages", [])),
        "theorem_count": len(result.get("theorems", [])),
    }


def verify_lean_project(file_map: dict, entry_file: str):
    start_time = time.time()
    lean_executable = find_lean_executable()
    if not lean_executable:
        end_time = time.time()
        return {
            "verified": False,
            "returnCode": -1,
            "theorems": [],
            "messages": [
                {
                    "file": entry_file,
                    "line": 0,
                    "column": 0,
                    "severity": "error",
                    "message": "Lean executable not found. Please install Lean 4 via elan.",
                }
            ],
            "feedback": {
                "stdout": "",
                "stderr": "Lean executable not found. Please install Lean 4 via elan.",
            },
            "processingTimeSeconds": round(end_time - start_time, 3),
        }

    with tempfile.TemporaryDirectory() as temp_dir:
        for rel_path, content in file_map.items():
            safe_rel_path = rel_path.strip().lstrip("/")
            full_path = os.path.join(temp_dir, safe_rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as file_handle:
                file_handle.write(content)

        safe_entry_file = entry_file.strip().lstrip('/').replace('\\', '/')
        entry_path = os.path.join(temp_dir, safe_entry_file)
        if not os.path.exists(entry_path):
            end_time = time.time()
            return {
                "verified": False,
                "returnCode": -1,
                "theorems": [],
                "messages": [
                    {
                        "file": safe_entry_file,
                        "line": 0,
                        "column": 0,
                        "severity": "error",
                        "message": f"Entry file not found in payload: {safe_entry_file}",
                    }
                ],
                "feedback": {
                    "stdout": "",
                    "stderr": f"Entry file not found in payload: {safe_entry_file}",
                },
                "processingTimeSeconds": round(end_time - start_time, 3),
            }

        try:
            env = os.environ.copy()
            existing_lean_path = env.get("LEAN_PATH", "")
            env["LEAN_PATH"] = f"{temp_dir}:{existing_lean_path}" if existing_lean_path else temp_dir

            result = subprocess.run(
                [lean_executable, safe_entry_file],
                capture_output=True,
                text=True,
                timeout=90,
                cwd=temp_dir,
                env=env,
            )

            verified = result.returncode == 0
            end_time = time.time()

            messages = parse_lean_messages(result.stdout, result.stderr, safe_entry_file)
            theorem_scan_code = file_map.get(safe_entry_file, "")
            theorems = parse_theorem_info(theorem_scan_code)

            return {
                "verified": verified,
                "returnCode": result.returncode,
                "theorems": theorems,
                "messages": messages,
                "feedback": {
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                },
                "processingTimeSeconds": round(end_time - start_time, 3),
            }
        except subprocess.TimeoutExpired:
            end_time = time.time()
            return {
                "verified": False,
                "returnCode": -1,
                "theorems": [],
                "messages": [
                    {
                        "file": safe_entry_file,
                        "line": 0,
                        "column": 0,
                        "severity": "error",
                        "message": "Project verification timeout after 90 seconds",
                    }
                ],
                "feedback": {
                    "stdout": "",
                    "stderr": "Project verification timeout after 90 seconds",
                },
                "processingTimeSeconds": round(end_time - start_time, 3),
            }
        except Exception as error:
            end_time = time.time()
            return {
                "verified": False,
                "returnCode": -1,
                "theorems": [],
                "messages": [
                    {
                        "file": safe_entry_file,
                        "line": 0,
                        "column": 0,
                        "severity": "error",
                        "message": str(error),
                    }
                ],
                "feedback": {
                    "stdout": "",
                    "stderr": str(error),
                },
                "processingTimeSeconds": round(end_time - start_time, 3),
            }


def to_compiler_project_response(file_map: dict, entry_file: str):
    result = verify_lean_project(file_map, entry_file)
    errors = [
        {
            "line": message.get("line", 0),
            "column": message.get("column", 0),
            "message": message.get("message", ""),
        }
        for message in result.get("messages", [])
        if message.get("severity") == "error"
    ]

    return {
        "valid": result.get("verified", False),
        "errors": errors,
        "processing_time_seconds": result.get("processingTimeSeconds", 0.0),
        "return_code": result.get("returnCode", -1),
        "message_count": len(result.get("messages", [])),
        "theorem_count": len(result.get("theorems", [])),
    }


def get_mathlib_info(declaration_name: str) -> dict:
    """
    Attempts to retrieve the Lean 4 source/type of a Mathlib4 declaration
    by running `#check <name>` and `#print <name>` via the lean executable.

    Requires the lean worker environment to have Mathlib4 pre-built (lake build).
    If Mathlib is not available or the declaration is unknown, returns found=False
    with a graceful error message rather than raising.

    Returns:
        {
            "declaration_name": str,
            "lean_source": str,   -- stdout captured from lean (empty if not found)
            "found": bool,
            "error_message": str, -- human-readable reason when found=False
            "processing_time_seconds": float,
        }
    """
    start_time = time.time()
    lean_executable = find_lean_executable()

    if not lean_executable:
        return {
            "declaration_name": declaration_name,
            "lean_source": "",
            "found": False,
            "error_message": "Lean executable not found. Please install Lean 4 via elan.",
            "processing_time_seconds": round(time.time() - start_time, 3),
        }

    lean_code = (
        "import Mathlib\n"
        f"#print {declaration_name}\n"
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        lean_file_path = os.path.join(temp_dir, "mathlib_lookup.lean")
        with open(lean_file_path, "w", encoding="utf-8") as fh:
            fh.write(lean_code)

        try:
            result = subprocess.run(
                [lean_executable, lean_file_path],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=temp_dir,
            )
        except subprocess.TimeoutExpired:
            return {
                "declaration_name": declaration_name,
                "lean_source": "",
                "found": False,
                "error_message": "Timeout: Mathlib lookup exceeded 120 seconds.",
                "processing_time_seconds": round(time.time() - start_time, 3),
            }
        except Exception as exc:
            return {
                "declaration_name": declaration_name,
                "lean_source": "",
                "found": False,
                "error_message": str(exc),
                "processing_time_seconds": round(time.time() - start_time, 3),
            }

    elapsed = round(time.time() - start_time, 3)
    combined = (result.stdout or "") + (result.stderr or "")

    # Heuristics to detect a "not found" response from lean.
    not_found_hints = [
        "unknown identifier",
        "unknown constant",
        "declaration not found",
        "error: unknown",
        "failed to synthesize",
    ]
    not_found = any(hint in combined.lower() for hint in not_found_hints)

    # Even a non-zero return code is treated as not found when the output
    # contains meaningful lean text (e.g. type errors from a bad import).
    if not_found or (result.returncode != 0 and not result.stdout.strip()):
        return {
            "declaration_name": declaration_name,
            "lean_source": "",
            "found": False,
            "error_message": combined.strip() or "Declaration not found in Mathlib.",
            "processing_time_seconds": elapsed,
        }

    return {
        "declaration_name": declaration_name,
        "lean_source": result.stdout.strip(),
        "found": True,
        "error_message": "",
        "processing_time_seconds": elapsed,
    }


# ---------------------------------------------------------------------------
# Mathlib Lineage / Dependency Graph
# ---------------------------------------------------------------------------

# Qualified names: must start with an uppercase letter and have at least one dot
# e.g. Nat.succ_pos, Real.sqrt_sq, Finset.sum_comm
_QUALIFIED_NAME_RE = re.compile(r'\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_\']+)+)\b')

# Lean built-in universe/sort keywords to exclude from deps
_LEAN_BUILTINS = frozenset({
    'Prop', 'Type', 'Sort', 'Bool', 'True', 'False', 'And', 'Or', 'Not',
    'Iff', 'Eq', 'Ne', 'HEq', 'Exists', 'Sigma', 'PSigma', 'Subtype',
    'List', 'Array', 'Option', 'Sum', 'Prod', 'Unit', 'Empty', 'String',
    'Int', 'Float', 'Char', 'IO', 'Lean', 'Std', 'Lake',
})

MAX_LINEAGE_NODES = 30
MAX_DEPS_PER_NODE = 10


def _get_lean_batch_prints(names: list) -> dict:
    """
    Run a single Lean process that issues `#print <name>` for every name.

    Returns a dict {name: printed_output} where printed_output is the
    portion of stdout that belongs to that declaration (empty string if
    the declaration was not found or lean errored for that entry).
    """
    if not names:
        return {}

    lean_executable = find_lean_executable()
    if not lean_executable:
        return {n: "" for n in names}

    lines = ["import Mathlib"]
    for name in names:
        lines.append(f"#print {name}")
    lean_code = "\n".join(lines) + "\n"

    with tempfile.TemporaryDirectory() as temp_dir:
        lean_file = os.path.join(temp_dir, "batch_print.lean")
        with open(lean_file, "w", encoding="utf-8") as fh:
            fh.write(lean_code)

        try:
            result = subprocess.run(
                [lean_executable, lean_file],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=temp_dir,
            )
        except (subprocess.TimeoutExpired, Exception):
            return {n: "" for n in names}

    # Lean4 #print output goes to stdout; combine with stderr to be safe (mirrors get_mathlib_info).
    stdout = (result.stdout or "") + (result.stderr or "")

    output_map = {n: "" for n in names}

    # Lean4 `#print Name` always emits a line like:
    #   theorem Name.{u} : type := body
    #   def Name.{u} : type := body
    # The declaration keyword is always at column 0.  We anchor to it so we
    # never accidentally match `Name` appearing inside another theorem's body.
    _DECL_KW = (
        r'(?:(?:protected|noncomputable|private)\s+)*'
        r'(?:theorem|def|abbrev|instance|structure|class|axiom|opaque|lemma)\s+'
    )
    positions = []
    for name in names:
        pat = re.compile(r'(?m)^' + _DECL_KW + re.escape(name) + r'(?=[.{\s(:])')
        m = pat.search(stdout)
        if m:
            # m.start() is the beginning of the declaration line ("theorem …")
            positions.append((m.start(), name))

    positions.sort(key=lambda t: t[0])

    not_found_hints = [
        "unknown identifier", "unknown constant",
        "declaration not found", "error: unknown",
    ]

    for i, (start_idx, name) in enumerate(positions):
        # Each start_idx is already at the beginning of a line, so the next
        # section's start_idx cleanly terminates the current section.
        end_idx = positions[i + 1][0] if i + 1 < len(positions) else len(stdout)
        section = stdout[start_idx:end_idx].strip()
        if section and not any(h in section.lower() for h in not_found_hints):
            output_map[name] = section

    return output_map


def _extract_deps(lean_source: str, self_name: str) -> list:
    """
    Extract qualified Lean names from a #print output, excluding the
    declaration itself and known built-ins.

    Returns up to MAX_DEPS_PER_NODE unique names.
    """
    seen = set()
    deps = []
    for match in _QUALIFIED_NAME_RE.finditer(lean_source):
        name = match.group(1)
        if (
            name != self_name
            and name not in _LEAN_BUILTINS
            and name not in seen
            and not self_name.startswith(name + ".")
        ):
            seen.add(name)
            deps.append(name)
            if len(deps) >= MAX_DEPS_PER_NODE:
                break
    return deps


def get_mathlib_lineage(declaration_name: str, depth: int = 2) -> dict:
    """
    Build a dependency graph for a Mathlib4 declaration by performing a
    BFS of #print calls, one Lean process per depth level.

    Returns:
        {
            "root": str,
            "nodes": [{ "id", "name", "lean_source", "found", "depth_level" }],
            "edges": [{ "source", "target" }],
            "total_nodes": int,
            "depth": int,
            "truncated": bool,
            "processing_time_seconds": float
        }
    """
    start_time = time.time()
    depth = max(1, min(4, depth))

    node_registry = {
        declaration_name: {
            "id": 1,
            "lean_source": "",
            "found": False,
            "depth_level": 0,
        }
    }
    edge_set = set()
    truncated = False
    next_id = 2

    for level in range(depth):
        to_print = [
            name for name, meta in node_registry.items()
            if meta["depth_level"] == level
        ]
        if not to_print:
            break

        batch = _get_lean_batch_prints(to_print)

        for name in to_print:
            printed = batch.get(name, "")
            found = bool(printed.strip())
            node_registry[name]["lean_source"] = printed
            node_registry[name]["found"] = found

            if not found or level >= depth - 1:
                continue

            if len(node_registry) >= MAX_LINEAGE_NODES:
                truncated = True
                continue

            deps = _extract_deps(printed, name)
            parent_id = node_registry[name]["id"]

            for dep in deps:
                if len(node_registry) >= MAX_LINEAGE_NODES:
                    truncated = True
                    break
                if dep not in node_registry:
                    node_registry[dep] = {
                        "id": next_id,
                        "lean_source": "",
                        "found": False,
                        "depth_level": level + 1,
                    }
                    next_id += 1
                dep_id = node_registry[dep]["id"]
                edge_set.add((parent_id, dep_id))

    elapsed = round(time.time() - start_time, 3)

    nodes = [
        {
            "id": meta["id"],
            "name": name,
            "lean_source": meta["lean_source"],
            "found": meta["found"],
            "depth_level": meta["depth_level"],
        }
        for name, meta in node_registry.items()
    ]
    nodes.sort(key=lambda n: n["id"])

    edges = [{"source": s, "target": t} for s, t in edge_set]

    return {
        "root": declaration_name,
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "depth": depth,
        "truncated": truncated,
        "processing_time_seconds": elapsed,
    }
