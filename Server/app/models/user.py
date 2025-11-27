import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.extensions import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text, unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    # 'projects_led' will be available via backref in Project
    # 'collaborations' will be available via the Association Table

    def __repr__(self):
        return f"<User {self.email}>"