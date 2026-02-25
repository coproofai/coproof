from marshmallow import Schema, fields, validate

class AgentRequestSchema(Schema):
    """
    Validation for triggering the AI Agent.
    Used in: POST /api/projects/{id}/nodes/{node_id}/agent/solve
    """
    # The user can optionally provide extra context or hints to the agent
    hint = fields.String(allow_none=True)
    strategy = fields.String(validate=validate.OneOf(["direct", "contradiction", "induction"]),  load_default="direct")

class AgentResponseSchema(Schema):
    """
    Validation for the Agent's output (before saving to DB/returning to UI).
    """
    next_step = fields.String(required=True)
    confidence_score = fields.Float(validate=validate.Range(min=0.0, max=1.0))
    suggested_lean_code = fields.String(allow_none=True)