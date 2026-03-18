import os
from datetime import timedelta

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_change_in_production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://coproof:coproofpass@db:5432/coproof_db')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt_secret_change_me')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_LEAN_QUEUE = os.environ.get('CELERY_LEAN_QUEUE', 'lean_queue')
    CELERY_GIT_ENGINE_QUEUE = os.environ.get('CELERY_GIT_ENGINE_QUEUE', 'git_engine_queue')
    REPO_STORAGE_PATH = os.environ.get('REPO_STORAGE_PATH', '/tmp/coproof-storage')
    GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID')
    GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET')
    GITHUB_OAUTH_SCOPES = "repo,read:user,user:email"

class DevelopmentConfig(Config):
    """Configuration for local development."""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """Configuration for automated tests."""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'postgresql://coproof:coproofpass@localhost:5432/coproof_test_db')
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = "NullCache"

class ProductionConfig(Config):
    """Configuration for production deployments."""
    DEBUG = False
    TESTING = False


def get_config_class(selected_config=None, default='development'):
    """Resolve the configuration class from environment variables or an explicit name."""
    config_name = (selected_config or os.environ.get('APP_CONFIG') or os.environ.get('FLASK_ENV') or default).strip().lower()
    config_map = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig,
    }

    if config_name not in config_map:
        valid_options = ', '.join(sorted(config_map.keys()))
        raise ValueError(f"Invalid APP_CONFIG '{config_name}'. Expected one of: {valid_options}")

    return config_map[config_name]