import os
from kombu import Exchange, Queue
from flask import Flask, jsonify
from flask_cors import CORS
from app.extensions import db, migrate, jwt, ma, socketio, celery, cache
from app.exceptions import CoProofError
from config import get_config_class


def create_app(config_class=None):
    """Create and configure the Flask application instance."""
    from dotenv import load_dotenv

    load_dotenv()
    selected_config = config_class or get_config_class(default='development')
    app = Flask(__name__)
    app.config.from_object(selected_config)

    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)
    cache.init_app(app)
    socketio.init_app(app, message_queue=app.config['REDIS_URL'])

    lean_queue = app.config['CELERY_LEAN_QUEUE']
    computation_queue = app.config['CELERY_COMPUTATION_QUEUE']
    cluster_computation_queue = app.config['CELERY_CLUSTER_COMPUTATION_QUEUE']
    git_engine_queue = app.config['CELERY_GIT_ENGINE_QUEUE']
    nl2fl_queue = app.config['CELERY_NL2FL_QUEUE']
    agents_queue = app.config['CELERY_AGENTS_QUEUE']
    app.config['CELERY_CONFIG'] = {
        'broker_url': app.config['CELERY_BROKER_URL'],
        'result_backend': app.config['CELERY_RESULT_BACKEND'],
        'task_default_queue': lean_queue,
        'task_queues': (
            Queue(lean_queue, Exchange(lean_queue, type='direct'), routing_key=lean_queue),
            Queue(computation_queue, Exchange(computation_queue, type='direct'), routing_key=computation_queue),
            Queue(cluster_computation_queue, Exchange(cluster_computation_queue, type='direct'), routing_key=cluster_computation_queue),
            Queue(git_engine_queue, Exchange(git_engine_queue, type='direct'), routing_key=git_engine_queue),
            Queue(nl2fl_queue, Exchange(nl2fl_queue, type='direct'), routing_key=nl2fl_queue),
            Queue(agents_queue, Exchange(agents_queue, type='direct'), routing_key=agents_queue),
        )
    }
    celery.conf.update(app.config['CELERY_CONFIG'])

    register_error_handlers(app)

    # @app.route('/health')
    # def health_check():
    #     return jsonify({"status": "healthy", "env": os.getenv('FLASK_ENV', 'unknown')}), 200

    from app.api.auth import auth_bp
    from app.api.projects import projects_bp
    from app.api.nodes import nodes_bp
    from app.api.agents import agent_bp
    from app.api.webhooks import webhooks_bp
    from app.api.translate import translate_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(nodes_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(translate_bp)

    return app


def register_error_handlers(app):
    """Register API-level exception handlers for common error responses."""
    @app.errorhandler(CoProofError)
    def handle_coproof_error(error):
        response = jsonify(error.to_dict())
        response.status_code = error.code
        return response

    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({"message": "Resource not found", "error_code": 404}), 404

    @app.errorhandler(500)
    def handle_500(error):
        return jsonify({"message": "Internal server error", "error_code": 500}), 500