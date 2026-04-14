from flask import Blueprint

# Define Blueprint
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/v1/webhooks')