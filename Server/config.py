import os
from datetime import timedelta

class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev_key_change_in_production')
    
    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://coproof_app_user:pass@localhost:5432/coproof_db')
    
    # JWT Auth
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt_secret_change_me')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    
    # Redis (Shared resource)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # Caching Config (Flask-Caching)
    CACHE_TYPE = "RedisCache"  
    CACHE_REDIS_URL = REDIS_URL 
    CACHE_DEFAULT_TIMEOUT = 300 # 5 minutes default
    
    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    
    # Stateless Git Engine Storage
    REPO_STORAGE_PATH = os.getenv('REPO_STORAGE_PATH', '/tmp/coproof-storage')

class DevelopmentConfig(Config):
    ENVIRONMENT_NAME    = 'development'
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
    WTF_CSRF_ENABLED = False
    # Use simple cache for tests to avoid needing Redis running
    CACHE_TYPE = "SimpleCache" 
    ENVIRONMENT_NAME = 'testing'

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    ENVIRONMENT_NAME = 'production'