import uuid
from sqlalchemy.dialects.postgresql import UUID, ENUM
from app.extensions import db

# Define Enum explicitly if using SQLAlchemy to create tables, 
# otherwise just use string or map to the existing DB type.
visibilidad_enum = ('publico', 'privado')

class Project(db.Model):
    __tablename__ = 'proyectos'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = db.Column(db.Text, nullable=False)
    descripcion = db.Column(db.Text)
    visibilidad = db.Column(db.Enum(*visibilidad_enum, name='proyecto_visibilidad'), nullable=False)
    lider_id = db.Column(UUID(as_uuid=True), db.ForeignKey('usuarios.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    
    # Relationships
    nodos = db.relationship('NodoGrafo', backref='proyecto', lazy='dynamic')

    def to_dict(self):
        return {
            'id': str(self.id),
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'visibilidad': self.visibilidad,
            'lider_id': str(self.lider_id)
        }