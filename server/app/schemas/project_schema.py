from app.extensions import ma
from app.models.project import Project
from marshmallow import fields, validate


class ProjectSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Project
        load_instance = True
        include_fk = True

    visibility = fields.String(validate=validate.OneOf(["public", "private"]))
    goal = fields.String(required=True)
    goal_imports = fields.List(fields.String(), required=False, allow_none=True)
    goal_definitions = fields.String(required=False, allow_none=True)
    tags = fields.List(fields.String(), required=False, allow_none=True)
    contributor_ids = fields.List(fields.UUID(), required=False, allow_none=True)
    url = fields.String(required=False, allow_none=True)
    remote_repo_url = fields.String(required=False, allow_none=True)
    default_branch = fields.String(required=False, allow_none=True)

    author = fields.Nested("UserSchema", only=("id", "full_name", "email"), dump_only=True)