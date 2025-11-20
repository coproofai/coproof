# app/models/user.py
import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.extensions import db

class User(db.Model):
    __tablename__ = 'usuarios'
    
    # Using UUIDs as defined in schema
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = db.Column(db.Text, nullable=False)
    correo = db.Column(db.Text, unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    correo_verificado = db.Column(db.Boolean, default=False)
    
    # Relationships
    configuracion = db.relationship('ConfiguracionUsuario', backref='usuario', uselist=False)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'nombre': self.nombre,
            'correo': self.correo
        }

