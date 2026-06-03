import logging

from flask import Blueprint, jsonify, request

from app.exceptions import CoProofError
from app.services.integrations.compiler_client import CompilerClient

logger = logging.getLogger(__name__)

lean_bp = Blueprint('lean', __name__, url_prefix='/api/v1/lean')


# ---------------------------------------------------------------------------
# POST /api/v1/lean/mathlib/lookup/submit
# ---------------------------------------------------------------------------
@lean_bp.route('/mathlib/lookup/submit', methods=['POST'])
def submit_mathlib_lookup():
    """
    Dispatch a Mathlib4 declaration lookup job to the lean worker.

    No authentication required — lookups are public.

    Body (JSON):
        declaration_name  str  required  e.g. "Nat.succ_pos"

    Returns 202 { task_id: str }
    """
    data = request.get_json(silent=True) or {}
    declaration_name = (data.get('declaration_name') or '').strip()

    if not declaration_name:
        return jsonify({"error": "declaration_name is required"}), 400

    try:
        task_id = CompilerClient.submit_mathlib_lookup(declaration_name)
        return jsonify({"task_id": task_id}), 202
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code


# ---------------------------------------------------------------------------
# GET /api/v1/lean/mathlib/lookup/<task_id>/result
# ---------------------------------------------------------------------------
@lean_bp.route('/mathlib/lookup/<task_id>/result', methods=['GET'])
def get_mathlib_lookup_result(task_id: str):
    """
    Poll the result of a previously submitted Mathlib lookup task.

    Returns 200 + MathlibLookupResult when complete:
        {
            "declaration_name": str,
            "lean_source":      str,
            "found":            bool,
            "error_message":    str,
            "processing_time_seconds": float
        }

    Returns 202 { status: 'pending' } while still running.
    """
    try:
        result = CompilerClient.get_mathlib_lookup_result(task_id)
        if result is None:
            return jsonify({"status": "pending"}), 202
        return jsonify(result), 200
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code


# ---------------------------------------------------------------------------
# POST /api/v1/lean/mathlib/lineage/submit
# ---------------------------------------------------------------------------
@lean_bp.route('/mathlib/lineage/submit', methods=['POST'])
def submit_mathlib_lineage():
    """
    Dispatch a Mathlib4 dependency-graph job to the lean worker.

    No authentication required — lineage lookups are public.

    Body (JSON):
        declaration_name  str  required  e.g. "Nat.exists_infinite_primes"
        depth             int  optional  1–4 (default 2)

    Returns 202 { task_id: str }
    """
    data = request.get_json(silent=True) or {}
    declaration_name = (data.get('declaration_name') or '').strip()
    depth = int(data.get('depth', 2))

    if not declaration_name:
        return jsonify({"error": "declaration_name is required"}), 400

    depth = max(1, min(4, depth))

    try:
        task_id = CompilerClient.submit_mathlib_lineage(declaration_name, depth)
        return jsonify({"task_id": task_id}), 202
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code


# ---------------------------------------------------------------------------
# GET /api/v1/lean/mathlib/lineage/<task_id>/result
# ---------------------------------------------------------------------------
@lean_bp.route('/mathlib/lineage/<task_id>/result', methods=['GET'])
def get_mathlib_lineage_result(task_id: str):
    """
    Poll the result of a previously submitted Mathlib lineage task.

    Returns 200 + LineageResult when complete:
        {
            "root":      str,
            "nodes":     [{ "id", "name", "lean_source", "found", "depth_level" }],
            "edges":     [{ "source", "target" }],
            "total_nodes": int,
            "depth":     int,
            "truncated": bool,
            "processing_time_seconds": float
        }

    Returns 202 { status: 'pending' } while still running.
    """
    try:
        result = CompilerClient.get_mathlib_lineage_result(task_id)
        if result is None:
            return jsonify({"status": "pending"}), 202
        return jsonify(result), 200
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code
