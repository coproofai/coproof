from flask import Blueprint

# Define Blueprint
agent_bp = Blueprint('agent', __name__, url_prefix='/api/v1/agents')