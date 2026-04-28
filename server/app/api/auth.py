from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from app.services.auth_service import AuthService
from app.services.github_service import GitHubService
from app.exceptions import CoProofError
from app.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

@auth_bp.route('/github/url', methods=['GET'])
def get_github_url():
    """
    Returns the URL for the 'Login with GitHub' button.
    Frontend should open this in a popup or redirect.
    """
    url = AuthService.get_github_auth_url()
    return jsonify({"url": url}), 200


@auth_bp.route('/github/callback', methods=['POST'])
def github_callback():
    """
    Frontend sends the 'code' received from GitHub here.
    """
    data = request.get_json()
    code = data.get('code')
    
    if not code:
        return jsonify({"error": "Missing code"}), 400
        
    result = AuthService.handle_github_callback(code)
    
    # Serialize User
    from app.schemas import UserSchema
    user_schema = UserSchema()
    
    return jsonify({
        "access_token": result['access_token'],
        "refresh_token": result['refresh_token'],
        "user": user_schema.dump(result['user'])
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Swaps a valid Refresh Token for a new Access Token.
    """
    current_user_id = get_jwt_identity()
    new_token = create_access_token(identity=current_user_id)
    return jsonify(access_token=new_token), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    """Return the current authenticated user's profile."""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    from app.schemas import UserSchema
    schema = UserSchema()
    return jsonify(schema.dump(user)), 200


@auth_bp.route('/github/invitations', methods=['GET'])
@jwt_required()
def get_github_invitations():
    """Return pending GitHub repository invitations for the current user."""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    token = AuthService.refresh_github_token_if_needed(user)
    if not token:
        return jsonify({"error": "No linked GitHub account."}), 400
    try:
        invitations = GitHubService.get_repo_invitations(token)
        simplified = [
            {
                "id": inv["id"],
                "repo": inv["repository"]["full_name"],
                "inviter": inv["inviter"]["login"] if inv.get("inviter") else None,
                "html_url": inv.get("html_url"),
            }
            for inv in invitations
        ]
        return jsonify({"invitations": simplified}), 200
    except CoProofError as e:
        return jsonify({"error": str(e)}), e.code


@auth_bp.route('/github/invitations/<int:invitation_id>/accept', methods=['POST'])
@jwt_required()
def accept_github_invitation(invitation_id):
    """Accept a pending GitHub repository invitation."""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    token = AuthService.refresh_github_token_if_needed(user)
    if not token:
        return jsonify({"error": "No linked GitHub account."}), 400
    try:
        GitHubService.accept_repo_invitation(token, invitation_id)
        return jsonify({"status": "accepted"}), 200
    except CoProofError as e:
        return jsonify({"error": str(e)}), e.code


@auth_bp.route('/github/invitations/<int:invitation_id>', methods=['DELETE'])
@jwt_required()
def decline_github_invitation(invitation_id):
    """Decline a pending GitHub repository invitation."""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    token = AuthService.refresh_github_token_if_needed(user)
    if not token:
        return jsonify({"error": "No linked GitHub account."}), 400
    try:
        GitHubService.decline_repo_invitation(token, invitation_id)
        return jsonify({"status": "declined"}), 200
    except CoProofError as e:
        return jsonify({"error": str(e)}), e.code
