import hmac
import hashlib
import os
from flask import Blueprint, request, jsonify, abort
from app.models.project import Project
from app.tasks.git_tasks import async_reindex_project

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/v1/webhooks')

@webhooks_bp.route('/github', methods=['POST'])
def github_webhook():
    """
    Receives 'push' events from GitHub to keep the DB Index in sync.
    """
    # 1. Verify Signature (Security)
    secret = os.environ.get('GITHUB_WEBHOOK_SECRET')
    signature = request.headers.get('X-Hub-Signature-256')
    
    if not secret or not signature:
        # If no secret configured, we might skip validation (Development) 
        # or abort (Production).
        if os.environ.get('FLASK_ENV') == 'production':
            abort(403, 'Webhook secret not configured or signature missing')
    
    if secret:
        # HMAC verification
        body_bytes = request.data
        local_signature = 'sha256=' + hmac.new(
            key=secret.encode('utf-8'), 
            msg=body_bytes, 
            digestmod=hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(local_signature, signature):
            abort(403, 'Invalid signature')

    # 2. Parse Payload
    event = request.headers.get('X-GitHub-Event', 'ping')
    if event == 'ping':
        return jsonify({'msg': 'pong'}), 200
        
    if event != 'push':
        # We only care about pushes for now
        return jsonify({'msg': 'ignored'}), 200

    payload = request.get_json()
    repo_url = payload.get('repository', {}).get('clone_url')
    
    if not repo_url:
        return jsonify({'msg': 'no repo url'}), 400

    # 3. Find Project in DB
    # We assume 1-to-1 mapping for now.
    project = Project.query.filter_by(remote_repo_url=repo_url).first()
    
    if not project:
        # Project not registered in CoProof
        return jsonify({'msg': 'project not found'}), 404

    # 4. Trigger Sync Task
    # This pulls the changes to /tmp and updates the SQL Index
    async_reindex_project.delay(str(project.id))

    return jsonify({'msg': 'sync triggered', 'project': project.name}), 200