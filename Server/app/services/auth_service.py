# app/services/auth_service.py
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from app.models.user import User
from app.extensions import db

def register_user(data):
    if User.query.filter_by(correo=data['correo']).first():
        return None, "Email already exists"
    
    new_user = User(
        nombre=data['nombre'],
        correo=data['correo'],
        password_hash=generate_password_hash(data['password'])
    )
    db.session.add(new_user)
    db.session.commit()
    # Logic to send verification email would go here (via Celery)
    return new_user, None

def login_user(email, password):
    user = User.query.filter_by(correo=email).first()
    if user and check_password_hash(user.password_hash, password):
        token = create_access_token(identity=str(user.id))
        return token, None
    return None, "Invalid credentials"