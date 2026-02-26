from app.extensions import ma
from app.models.new_project import NewProject
from marshmallow import fields, validate

class ProjectSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = NewProject
        load_instance = True
        include_fk = True 
    
    # Custom validations
    visibility = fields.String(validate=validate.OneOf(["public", "private"]))
    goal = fields.String(required=True)
    
    # Nested author info (ReadOnly)
    # Reference by string name to avoid circular import issues with __init__
    author = fields.Nested("UserSchema", only=("id", "full_name", "email"), dump_only=True)
    
    # Git info
    remote_repo_url = fields.Url(required=True)