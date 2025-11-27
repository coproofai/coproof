from app.extensions import ma
from app.models.user import User
from app.models.graph_index import GraphNode
from marshmallow import fields, validate

# 1. Define Common/Shared Schemas
class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        exclude = ("password_hash",) 

class GraphNodeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = GraphNode
        load_instance = True
        include_fk = True
    
    status = fields.String(validate=validate.OneOf(["pending", "in_review", "verified", "error"]))
    node_type = fields.String(validate=validate.OneOf(["global_goal", "theorem", "lemma", "corollary", "definition", "numerical_eval"]))
    
    # Read-only Git metadata
    commit_hash = fields.String(dump_only=True)

# 2. Import Sub-Schemas
# We import these AFTER defining UserSchema so that ProjectSchema can find 'UserSchema' in the registry if needed
from app.schemas.project_schema import ProjectSchema
from app.schemas.agent_schema import AgentRequestSchema, AgentResponseSchema

# 3. Export all for clean imports in Services/API
__all__ = [
    'UserSchema',
    'GraphNodeSchema',
    'ProjectSchema',
    'AgentRequestSchema',
    'AgentResponseSchema'
]