import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError

from app.exceptions import CoProofError
from app.extensions import db
from app.models.user_api_key import UserApiKey
from app.services.integrations.translate_client import TranslateClient

logger = logging.getLogger(__name__)

translate_bp = Blueprint('translate', __name__, url_prefix='/api/v1/translate')

# ---------------------------------------------------------------------------
# Static catalogue of supported OpenRouter models
# ---------------------------------------------------------------------------
# Model IDs use the format "<provider>/<model-name>" where provider determines
# which native API is called (openai, anthropic, google, deepseek, github).
AVAILABLE_MODELS = [
    # OpenAI
    {"id": "openai/gpt-4o",                        "name": "GPT-4o",                 "provider": "OpenAI"},
    {"id": "openai/gpt-4o-mini",                   "name": "GPT-4o Mini",            "provider": "OpenAI"},
    {"id": "openai/o4-mini",                       "name": "o4 Mini",               "provider": "OpenAI"},
    # Anthropic
    {"id": "anthropic/claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet",     "provider": "Anthropic"},
    {"id": "anthropic/claude-3-haiku-20240307",    "name": "Claude 3 Haiku",        "provider": "Anthropic"},
    # Google
    {"id": "google/gemini-flash-lite-latest",       "name": "Gemini Flash Lite",     "provider": "Google"},
    # DeepSeek
    {"id": "deepseek/deepseek-chat",               "name": "DeepSeek Chat (V3)",    "provider": "DeepSeek"},
    {"id": "deepseek/deepseek-reasoner",           "name": "DeepSeek Reasoner (R1)","provider": "DeepSeek"},
    # GitHub Models (requires a GitHub PAT — github.com/settings/tokens)
    {"id": "github/openai/gpt-4o",                 "name": "GPT-4o (GitHub)",        "provider": "GitHub"},
    {"id": "github/openai/gpt-4o-mini",            "name": "GPT-4o Mini (GitHub)",   "provider": "GitHub"},
    # Mock — skips the LLM call, returns a hardcoded Lean proof for pipeline testing
    {"id": "mock/test",                            "name": "Mock (Pipeline Test)",   "provider": "Mock"},
]


# ---------------------------------------------------------------------------
# POST /api/v1/translate/submit
# ---------------------------------------------------------------------------
@translate_bp.route('/submit', methods=['POST'])
@jwt_required(optional=True)
def submit_translation():
    """
    Dispatch a natural-language → Lean 4 translation task.

    Optional JWT: when authenticated, the user's saved API key for the
    requested model is loaded automatically (unless overridden in the body).

    Body (JSON):
        natural_text  str  required
        model_id      str  required
        api_key       str  optional  (required if user has no saved key)
        max_retries   int  optional  (default 3, range 1-10)
        system_prompt str  optional

    Returns 202 { task_id: str }
    """
    data = request.get_json(silent=True) or {}

    natural_text = (data.get('natural_text') or '').strip()
    model_id = (data.get('model_id') or '').strip()
    api_key = (data.get('api_key') or '').strip()
    max_retries = data.get('max_retries', 3)
    system_prompt = data.get('system_prompt')
    definitions_content = data.get('definitions_content') or None

    if not natural_text:
        return jsonify({"error": "natural_text is required"}), 400
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400

    # Validate max_retries
    try:
        max_retries = int(max_retries)
        if not (1 <= max_retries <= 10):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "max_retries must be an integer between 1 and 10"}), 400

    # If no api_key in body, try to load from user's saved keys
    user_id = get_jwt_identity()
    logger.debug('[translate/submit] body api_key present=%s len=%d user_id=%s',
                 bool(api_key), len(api_key), user_id)
    if not api_key:
        if user_id:
            record = UserApiKey.query.filter_by(
                user_id=user_id, model_id=model_id
            ).first()
            if record:
                try:
                    api_key = record.decrypt_key().strip()
                    logger.debug('[translate/submit] loaded key from DB len=%d prefix=%s',
                                 len(api_key), api_key[:8] if api_key else 'EMPTY')
                except Exception as exc:
                    logger.warning('Failed to decrypt API key for user %s model %s: %s',
                                   user_id, model_id, exc)
            else:
                logger.debug('[translate/submit] no DB record for user=%s model=%s', user_id, model_id)
        else:
            logger.debug('[translate/submit] no JWT identity, cannot load key from DB')

    logger.debug('[translate/submit] final api_key present=%s len=%d',
                 bool(api_key), len(api_key))

    if not api_key:
        return jsonify({
            "error": "api_key is required (provide in body or save one for this model)"
        }), 400

    payload = {
        "natural_text": natural_text,
        "model_id": model_id,
        "api_key": api_key,
        "max_retries": max_retries,
    }
    if system_prompt:
        payload["system_prompt"] = system_prompt
    if definitions_content:
        payload["definitions_content"] = definitions_content

    try:
        task_id = TranslateClient.submit(payload)
        return jsonify({"task_id": task_id}), 202
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code


# ---------------------------------------------------------------------------
# GET /api/v1/translate/<task_id>/result
# ---------------------------------------------------------------------------
@translate_bp.route('/<task_id>/result', methods=['GET'])
def get_translation_result(task_id: str):
    """
    Poll the result of a previously submitted translation task.

    Returns 200 + TranslationResult when complete.
    Returns 202 { status: 'pending' } while still running.
    """
    try:
        result = TranslateClient.get_result(task_id)
        if result is None:
            return jsonify({"status": "pending"}), 202
        return jsonify(result), 200
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code


# ---------------------------------------------------------------------------
# GET /api/v1/translate/models
# ---------------------------------------------------------------------------
@translate_bp.route('/models', methods=['GET'])
def get_models():
    """Return the static list of supported OpenRouter models."""
    return jsonify(AVAILABLE_MODELS), 200


# ---------------------------------------------------------------------------
# POST /api/v1/translate/api-key
# ---------------------------------------------------------------------------
@translate_bp.route('/api-key', methods=['POST'])
@jwt_required()
def save_api_key():
    """
    Save (or update) an encrypted API key for a model.

    Body (JSON):
        model_id  str  required
        api_key   str  required  (raw key; never stored in plaintext)
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    model_id = (data.get('model_id') or '').strip()
    raw_key = (data.get('api_key') or '').strip()

    if not model_id:
        return jsonify({"error": "model_id is required"}), 400
    if not raw_key:
        return jsonify({"error": "api_key is required"}), 400

    # Upsert: update if exists, create if not
    record = UserApiKey.query.filter_by(user_id=user_id, model_id=model_id).first()
    try:
        if record:
            record.update_key(raw_key)
        else:
            record = UserApiKey.create(
                user_id=user_id, model_id=model_id, raw_key=raw_key
            )
            db.session.add(record)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Failed to save API key due to a conflict"}), 409
    except Exception as e:
        db.session.rollback()
        logger.error('save_api_key error for user %s model %s: %s', user_id, model_id, e)
        return jsonify({"error": "Failed to save API key"}), 500

    return jsonify({
        "model_id": model_id,
        "masked_key": record.masked_key(),
        "has_key": True,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/v1/translate/api-key/<model_id>
# ---------------------------------------------------------------------------
@translate_bp.route('/api-key/<path:model_id>', methods=['GET'])
@jwt_required()
def get_api_key_status(model_id: str):
    """
    Return the masked API key for the given model, or has_key: false.

    The model_id may contain '/' (e.g. "openai/gpt-4o"), hence path converter.
    """
    user_id = get_jwt_identity()

    record = UserApiKey.query.filter_by(user_id=user_id, model_id=model_id).first()
    if not record:
        return jsonify({
            "model_id": model_id,
            "masked_key": None,
            "has_key": False,
        }), 200

    return jsonify({
        "model_id": model_id,
        "masked_key": record.masked_key(),
        "has_key": True,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/v1/translate/fl2nl/submit
# ---------------------------------------------------------------------------
@translate_bp.route('/fl2nl/submit', methods=['POST'])
@jwt_required(optional=True)
def submit_fl2nl():
    """
    Dispatch a Lean 4 → natural-language translation task.

    Body (JSON):
        lean_code     str  required   – Lean 4 source to describe
        model_id      str  required
        api_key       str  optional   (required if user has no saved key)
        system_prompt str  optional

    Returns 202 { task_id: str }
    """
    data = request.get_json(silent=True) or {}

    lean_code = (data.get('lean_code') or '').strip()
    model_id = (data.get('model_id') or '').strip()
    api_key = (data.get('api_key') or '').strip()
    system_prompt = data.get('system_prompt')

    if not lean_code:
        return jsonify({"error": "lean_code is required"}), 400
    if not model_id:
        return jsonify({"error": "model_id is required"}), 400

    # Load saved key from DB if not provided
    user_id = get_jwt_identity()
    if not api_key and user_id:
        record = UserApiKey.query.filter_by(user_id=user_id, model_id=model_id).first()
        if record:
            try:
                api_key = record.decrypt_key().strip()
            except Exception as exc:
                logger.warning('Failed to decrypt API key for user %s model %s: %s',
                               user_id, model_id, exc)

    if not api_key:
        return jsonify({
            "error": "api_key is required (provide in body or save one for this model)"
        }), 400

    payload = {
        "lean_code": lean_code,
        "model_id": model_id,
        "api_key": api_key,
    }
    if system_prompt:
        payload["system_prompt"] = system_prompt

    try:
        task_id = TranslateClient.submit_fl2nl(payload)
        return jsonify({"task_id": task_id}), 202
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code


# ---------------------------------------------------------------------------
# GET /api/v1/translate/fl2nl/<task_id>/result
# ---------------------------------------------------------------------------
@translate_bp.route('/fl2nl/<task_id>/result', methods=['GET'])
def get_fl2nl_result(task_id: str):
    """
    Poll the result of a FL→NL translation task.

    Returns 200 + { natural_text, processing_time_seconds } when complete.
    Returns 202 { status: 'pending' } while still running.
    """
    try:
        result = TranslateClient.get_fl2nl_result(task_id)
        if result is None:
            return jsonify({"status": "pending"}), 202
        return jsonify(result), 200
    except CoProofError as e:
        return jsonify({"error": e.message}), e.code
