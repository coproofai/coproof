import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.exceptions import CoProofError
from app.models.user_api_key import UserApiKey
from app.services.integrations.agents_client import AgentsClient

logger = logging.getLogger(__name__)

agent_bp = Blueprint('agent', __name__, url_prefix='/api/v1/agents')


# ---------------------------------------------------------------------------
# POST /api/v1/agents/suggest/submit
# ---------------------------------------------------------------------------
@agent_bp.route('/suggest/submit', methods=['POST'])
@jwt_required(optional=True)
def submit_suggest():
    """
    Dispatch a natural-language suggestion task to the agents worker.

    Optional JWT: when authenticated, the user's saved API key for the
    requested model is loaded automatically (unless overridden in the body).

    Body (JSON):
        prompt        str  required
        model_id      str  required
        api_key       str  optional  (required if user has no saved key)
        system_prompt str  optional
        context       str  optional  (extra context prepended to the user message)

    Returns 202 { task_id: str }
    """
    data = request.get_json(silent=True) or {}

    prompt = (data.get('prompt') or '').strip()
    model_id = (data.get('model_id') or '').strip()
    api_key = (data.get('api_key') or '').strip()
    system_prompt = data.get('system_prompt')
    context = data.get('context')

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400

    # If no api_key in body, try to load from user's saved keys
    user_id = get_jwt_identity()
    logger.debug('[agents/submit] body api_key present=%s len=%d user_id=%s',
                 bool(api_key), len(api_key), user_id)
    if not api_key:
        if user_id:
            record = UserApiKey.query.filter_by(
                user_id=user_id, model_id=model_id
            ).first()
            if record:
                try:
                    api_key = record.decrypt_key().strip()
                    logger.debug('[agents/submit] loaded key from DB len=%d prefix=%s',
                                 len(api_key), api_key[:8] if api_key else 'EMPTY')
                except Exception as exc:
                    logger.warning('Failed to decrypt API key for user %s model %s: %s',
                                   user_id, model_id, exc)
            else:
                logger.debug('[agents/submit] no DB record for user=%s model=%s', user_id, model_id)
        else:
            logger.debug('[agents/submit] no JWT identity, cannot load key from DB')

    logger.debug('[agents/submit] final api_key present=%s len=%d',
                 bool(api_key), len(api_key))

    if not api_key:
        return jsonify({
            "error": "api_key is required (provide in body or save one for this model)"
        }), 400

    payload = {
        "prompt": prompt,
        "model_id": model_id,
        "api_key": api_key,
    }
    if system_prompt:
        payload["system_prompt"] = system_prompt
    if context:
        payload["context"] = context

    try:
        task_id = AgentsClient.submit(payload)
        return jsonify({"task_id": task_id}), 202
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code


# ---------------------------------------------------------------------------
# GET /api/v1/agents/suggest/<task_id>/result
# ---------------------------------------------------------------------------
@agent_bp.route('/suggest/<task_id>/result', methods=['GET'])
def get_suggest_result(task_id: str):
    """
    Poll the result of a previously submitted suggestion task.

    Returns 200 + SuggestResult when complete.
    Returns 202 { status: 'pending' } while still running.
    """
    try:
        result = AgentsClient.get_result(task_id)
        if result is None:
            return jsonify({"status": "pending"}), 202
        return jsonify(result), 200
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code
