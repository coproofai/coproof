from marshmallow import fields, validate

from app.extensions import ma
from app.models.graph_node import GraphNode


class GraphNodeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = GraphNode
        load_instance = True
        include_fk = True

    status = fields.String(validate=validate.OneOf(["pending", "in_review", "verified", "error"]))
    node_type = fields.String(validate=validate.OneOf(["global_goal", "theorem", "lemma", "corollary", "definition", "numerical_eval"]))

    commit_hash = fields.String(dump_only=True)