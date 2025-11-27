from app.extensions import ma
from app.models.project import Project
from marshmallow import fields, validate

class ProjectSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Project
        load_instance = True
        include_fk = True 
    
    # Custom validations
    visibility = fields.String(validate=validate.OneOf(["public", "private"]))
    
    # Nested Leader info (ReadOnly)
    # Reference by string name to avoid circular import issues with __init__
    leader = fields.Nested("UserSchema", only=("id", "full_name", "email"), dump_only=True)
    
    # Git info
    remote_repo_url = fields.Url(allow_none=True)