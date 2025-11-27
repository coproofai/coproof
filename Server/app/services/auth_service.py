from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from app.models.user import User
from app.extensions import db
from app.exceptions import CoProofError

class AuthService:
    @staticmethod
    def register_user(data):
        """
        Registers a new user.
        Raises error if email exists.
        """
        if User.query.filter_by(email=data['email']).first():
            raise CoProofError("Email already exists", code=400)
        
        new_user = User(
            full_name=data['full_name'],
            email=data['email'],
            password_hash=generate_password_hash(data['password'])
        )
        
        db.session.add(new_user)
        db.session.commit()
        return new_user

    @staticmethod
    def login_user(email, password):
        """
        Authenticates user and returns JWT token.
        """
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            raise CoProofError("Invalid credentials", code=401)
            
        # Create JWT (Identity is the UUID)
        access_token = create_access_token(identity=str(user.id))
        return {
            "access_token": access_token,
            "user": user
        }