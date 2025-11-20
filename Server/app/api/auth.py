from flask import Blueprint, request, jsonify
from app.services import auth_service
from flask_jwt_extended import jwt_required, get_jwt_identity, current_user

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    user, error = auth_service.register_user(data)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"message": "User created", "userId": user.to_dict()['id']}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    token, error = auth_service.login_user(data.get('correo'), data.get('password'))
    if error:
        return jsonify({"error": error}), 401
    return jsonify({"access_token": token}), 200