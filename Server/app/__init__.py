from flask import Flask
from app.extensions import db, jwt, migrate, cache, celery
from config import DevelopmentConfig

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    
    # Configure Celery
    app.config['CELERY_CONFIG'] = {
        'broker_url': app.config['CELERY_BROKER_URL'],
        'result_backend': app.config['CELERY_RESULT_BACKEND']
    }
    celery.conf.update(app.config['CELERY_CONFIG'])

    # Register Blueprints
    from app.api.auth import auth_bp
    from app.api.projects import projects_bp
    from app.api.proofs import proofs_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(proofs_bp)
    
    # Global Error Handlers can be added here

    return app