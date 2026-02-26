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
            result = subprocess.run(
                [lean_executable, safe_entry_file],
                capture_output=True,
                text=True,
                timeout=90,
                cwd=temp_dir,
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


