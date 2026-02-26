from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from app.services.auth_service import AuthService
from app.schemas import UserSchema
from app.exceptions import CoProofError

# Create Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

# @auth_bp.route('/register', methods=['POST'])
# def register():
#     data = request.get_json() or {}
    
#     # Service call
#     user = AuthService.register_user(data)
    
#     # Serialization
#     user_schema = UserSchema()
#     return jsonify({
#         "message": "User registered successfully",
#         "user": user_schema.dump(user)
#     }), 201

# @auth_bp.route('/login', methods=['POST'])
# def login():
#     data = request.get_json() or {}
#     email = data.get('email')
#     password = data.get('password')
    
#     # Service call
#     result = AuthService.login_user(email, password)
    
#     # Result contains access_token and user object
#     user_schema = UserSchema()
#     return jsonify({
#         "access_token": result['access_token'],
#         "user": user_schema.dump(result['user'])
#     }), 200


# @auth_bp.route('/me', methods=['GET'])
# def get_me():
#     # TODO: Implement protected route logic with @jwt_required()
#     # For Phase 5 initial setup, we focus on public auth endpoints
#     return jsonify({"message": "Profile endpoint placeholder"}), 501


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
@jwt_required(refresh=True) # Requires the "refresh_token" in Authorization header
def refresh():
    """
    Swaps a valid Refresh Token for a new Access Token.
    """
    current_user_id = get_jwt_identity()
    new_token = create_access_token(identity=current_user_id)
    return jsonify(access_token=new_token), 200
