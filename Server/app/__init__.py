import os
from kombu import Exchange, Queue
from flask import Flask, jsonify
from app.extensions import db, migrate, jwt, ma, socketio, celery, cache # <-- ADD cache
from app.exceptions import CoProofError
from config import DevelopmentConfig, TestingConfig


def create_app(config_class=DevelopmentConfig):
    """
    Application Factory Pattern.
    """
    from dotenv import load_dotenv
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(config_class)
    # Initialize Extensions
    
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)
    cache.init_app(app) 
    socketio.init_app(app, message_queue=app.config['REDIS_URL'])
    
    # Initialize Celery
    git_queue = app.config['CELERY_GIT_ENGINE_QUEUE']
    lean_queue = app.config['CELERY_LEAN_QUEUE']
    app.config['CELERY_CONFIG'] = {
        'broker_url': app.config['CELERY_BROKER_URL'],
        'result_backend': app.config['CELERY_RESULT_BACKEND'],
        'task_default_queue': git_queue,
        'task_queues': (
            Queue(git_queue, Exchange(git_queue, type='direct'), routing_key=git_queue),
            Queue(lean_queue, Exchange(lean_queue, type='direct'), routing_key=lean_queue),
        ),
        'task_routes': {
            'app.tasks.*': {'queue': git_queue},
        },
    }
    celery.conf.update(app.config['CELERY_CONFIG'])

    register_error_handlers(app)

    @app.route('/health')
    def health_check():
        return jsonify({"status": "healthy", "env": os.getenv('FLASK_ENV', 'unkown')}), 200

    #TODO: Check all blueprints are registered here
    from app.api.auth import auth_bp
    from app.api.projects import projects_bp
    from app.api.nodes import nodes_bp
    from app.api.agent_interaction import agent_bp 
    from app.api.webhooks import webhooks_bp       
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(nodes_bp)
    app.register_blueprint(agent_bp)    
    app.register_blueprint(webhooks_bp) 



    return app

def register_error_handlers(app):
    # ... (Same as before)
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