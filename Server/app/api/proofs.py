from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.tasks import run_proof_validation, run_agent_generation

proofs_bp = Blueprint('proofs', __name__, url_prefix='/api/v1')

@proofs_bp.route('/proofs/upload-external', methods=['POST'])
@jwt_required()
def upload_external_proof():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    # 1. Save file to S3/Local storage
    file_path = f"/tmp/{file.filename}" 
    file.save(file_path)
    
    # 2. Trigger Async Task
    task = run_proof_validation.delay(file_path)
    
    return jsonify({"message": "Upload successful, processing started", "jobId": task.id}), 202

@proofs_bp.route('/projects/<uuid:pid>/nodes/<uuid:nid>/agent/generate-proof', methods=['POST'])
@jwt_required()
def request_agent_proof(pid, nid):
    # Trigger AI Agent
    task = run_agent_generation.delay(str(pid), str(nid))
    return jsonify({"message": "Agent activated", "jobId": task.id}), 202