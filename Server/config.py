import os
from datetime import timedelta

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_change_in_production')
    
    # Database (Updated to match docker-compose credentials)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://coproof:coproofpass@localhost:5432/coproof_db')
    
    # JWT Auth
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt_secret_change_me')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    
    # Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Caching Config
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300 
    
    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    
    # Stateless Git Engine Storage
    REPO_STORAGE_PATH = os.environ.get('REPO_STORAGE_PATH', '/tmp/coproof-storage')

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    # FIXED: Point to Postgres instead of SQLite
    # We use a separate DB name 'coproof_test_db' to avoid wiping development data
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'postgresql://coproof:coproofpass@localhost:5432/coproof_test_db')
    WTF_CSRF_ENABLED = False
    # Use SimpleCache for tests to avoid Redis dependency if possible, 
    # but since we have Redis running for dev, we can use it or NullCache.
    CACHE_TYPE = "NullCache" 

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False