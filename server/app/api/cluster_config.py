import time

import requests as http_requests
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models.user_api_key import UserApiKey

cluster_bp = Blueprint('cluster', __name__, url_prefix='/api/v1/cluster')

# Virtual model-ids used to store cluster config inside UserApiKey
_URL_MODEL_ID = 'cluster/url'
_KEY_MODEL_ID = 'cluster/key'

_HEALTHCHECK_SOURCE = """\
def compute(data, target):
    register_record(test=True, status='ok')
    return {'evidence': 'healthcheck', 'sufficient': True}
"""

_TERMINAL_STATES = {
    'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL'
}


def _get_stored(user_id: str, model_id: str) -> str:
    rec = UserApiKey.query.filter_by(user_id=user_id, model_id=model_id).first()
    return rec.decrypt_key() if rec else ''


def _upsert(user_id: str, model_id: str, value: str) -> None:
    rec = UserApiKey.query.filter_by(user_id=user_id, model_id=model_id).first()
    if rec:
        rec.update_key(value)
    else:
        rec = UserApiKey.create(user_id=user_id, model_id=model_id, raw_key=value)
        db.session.add(rec)


# ---------------------------------------------------------------------------
# GET /api/v1/cluster/config
# ---------------------------------------------------------------------------

@cluster_bp.get('/config')
@jwt_required()
def get_config():
    user_id = get_jwt_identity()
    cluster_url = _get_stored(user_id, _URL_MODEL_ID)
    key_rec = UserApiKey.query.filter_by(user_id=user_id, model_id=_KEY_MODEL_ID).first()
    return jsonify({
        'url': cluster_url,
        'has_key': bool(key_rec),
        'masked_key': key_rec.masked_key() if key_rec else '',
    })


# ---------------------------------------------------------------------------
# PUT /api/v1/cluster/config
# ---------------------------------------------------------------------------

@cluster_bp.put('/config')
@jwt_required()
def save_config():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    cluster_url = (data.get('url') or '').strip()
    api_key = (data.get('api_key') or '').strip()

    if not cluster_url and not api_key:
        return jsonify({'error': 'Provide at least url or api_key'}), 400

    if cluster_url:
        _upsert(user_id, _URL_MODEL_ID, cluster_url)
    if api_key:
        _upsert(user_id, _KEY_MODEL_ID, api_key)

    db.session.commit()
    return jsonify({'status': 'saved'})


# ---------------------------------------------------------------------------
# POST /api/v1/cluster/healthcheck
# ---------------------------------------------------------------------------

@cluster_bp.post('/healthcheck')
@jwt_required()
def healthcheck():
    """
    Two-step smoke test:
      1. GET {url}/health   — connectivity check
      2. POST /jobs + poll  — proves Slurm is running and the API key is valid

    Body (all optional — falls back to saved config):
        url     str
        api_key str
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    cluster_url = (data.get('url') or '').strip() or _get_stored(user_id, _URL_MODEL_ID)
    api_key = (data.get('api_key') or '').strip() or _get_stored(user_id, _KEY_MODEL_ID)

    if not cluster_url:
        return jsonify({'ok': False, 'step': 'config', 'error': 'No cluster URL configured'}), 400

    base_url = cluster_url.rstrip('/')
    auth_headers: dict = {}
    if api_key:
        auth_headers['X-API-Key'] = api_key

    # --- Step 1: /health ---------------------------------------------------
    try:
        t0 = time.perf_counter()
        hr = http_requests.get(f'{base_url}/health', timeout=10)
        health_ms = round((time.perf_counter() - t0) * 1000)
        hr.raise_for_status()
    except Exception as exc:
        return jsonify({'ok': False, 'step': 'health', 'error': str(exc)}), 200

    # --- Step 2: submit trivial job ----------------------------------------
    payload = {
        'language': 'python',
        'source_code': _HEALTHCHECK_SOURCE,
        'entrypoint': 'compute',
        'input_data': None,
        'target': None,
        'timeout_seconds': 60,
    }
    try:
        sr = http_requests.post(
            f'{base_url}/jobs',
            json=payload,
            headers={**auth_headers, 'Content-Type': 'application/json'},
            timeout=15,
        )
        sr.raise_for_status()
        job_id = sr.json().get('job_id')
        if not job_id:
            return jsonify({'ok': False, 'step': 'submit', 'error': 'No job_id returned'}), 200
    except Exception as exc:
        return jsonify({'ok': False, 'step': 'submit', 'error': str(exc)}), 200

    # --- Step 3: poll until terminal ---------------------------------------
    deadline = time.perf_counter() + 90
    slurm_state = 'UNKNOWN'
    result = None

    while time.perf_counter() < deadline:
        try:
            pr = http_requests.get(
                f'{base_url}/jobs/{job_id}',
                headers=auth_headers,
                timeout=10,
            )
            pr.raise_for_status()
            body = pr.json()
            slurm_state = body.get('status', 'UNKNOWN').upper()
            if slurm_state in _TERMINAL_STATES:
                result = body.get('result')
                break
            time.sleep(3)
        except Exception as exc:
            return jsonify({'ok': False, 'step': 'poll', 'error': str(exc)}), 200

    if result is None:
        return jsonify({
            'ok': False,
            'step': 'poll',
            'error': f'Timed out waiting for job {job_id}; last state: {slurm_state}',
        }), 200

    completed = bool(result.get('completed'))
    return jsonify({
        'ok': completed,
        'health_response_ms': health_ms,
        'slurm_job_id': result.get('slurm_job_id'),
        'slurm_state': slurm_state,
        'rank_hosts': result.get('rank_hosts', {}),
        'records_count': len(result.get('records') or []),
        'error': result.get('error') if not completed else None,
    })


# ---------------------------------------------------------------------------
# GET /api/v1/cluster/nodes  — proxy sinfo via cluster REST API
# ---------------------------------------------------------------------------

@cluster_bp.get('/nodes')
@jwt_required()
def cluster_nodes():
    user_id = get_jwt_identity()
    cluster_url = _get_stored(user_id, _URL_MODEL_ID).rstrip('/')
    api_key = _get_stored(user_id, _KEY_MODEL_ID)
    if not cluster_url:
        return jsonify({'error': 'No cluster URL configured'}), 400
    headers: dict = {'Content-Type': 'application/json'}
    if api_key:
        headers['X-API-Key'] = api_key
    try:
        r = http_requests.get(f'{cluster_url}/nodes', headers=headers, timeout=10)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as exc:
        return jsonify({'error': str(exc)}), 502


# ---------------------------------------------------------------------------
# GET /api/v1/cluster/queue  — proxy squeue via cluster REST API
# ---------------------------------------------------------------------------

@cluster_bp.get('/queue')
@jwt_required()
def cluster_queue():
    user_id = get_jwt_identity()
    cluster_url = _get_stored(user_id, _URL_MODEL_ID).rstrip('/')
    api_key = _get_stored(user_id, _KEY_MODEL_ID)
    if not cluster_url:
        return jsonify({'error': 'No cluster URL configured'}), 400
    headers: dict = {'Content-Type': 'application/json'}
    if api_key:
        headers['X-API-Key'] = api_key
    try:
        r = http_requests.get(f'{cluster_url}/queue', headers=headers, timeout=10)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as exc:
        return jsonify({'error': str(exc)}), 502
