from flask import Blueprint, request, jsonify
from app.services.auth_service import AuthService
from app.schemas import UserSchema
from app.exceptions import CoProofError

# Create Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    
    # Service call
    user = AuthService.register_user(data)
    
    # Serialization
    user_schema = UserSchema()
    return jsonify({
        "message": "User registered successfully",
        "user": user_schema.dump(user)
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    
    # Service call
    result = AuthService.login_user(email, password)
    
    # Result contains access_token and user object
    user_schema = UserSchema()
    return jsonify({
        "access_token": result['access_token'],
        "user": user_schema.dump(result['user'])
    }), 200

@auth_bp.route('/me', methods=['GET'])
def get_me():
    # TODO: Implement protected route logic with @jwt_required()
    # For Phase 5 initial setup, we focus on public auth endpoints
    return jsonify({"message": "Profile endpoint placeholder"}), 501