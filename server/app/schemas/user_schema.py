from app.extensions import ma
from app.models.user import User
from marshmallow import fields


class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        exclude = ("password_hash", "github_access_token", "github_refresh_token", "token_expires_at")