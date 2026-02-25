import os
from datetime import timedelta

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_change_in_production')
    
    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # FIX: Use the Docker service name 'db' instead of 'localhost'
    # The app will connect to the 'db' service on the internal Docker network.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://coproof:coproofpass@db:5432/coproof_db')
    
    # JWT Auth
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt_secret_change_me')
    JWT_ACCESS_TOKEN_EXPRES = timedelta(hours=1)
    
    # Redis
    # FIX: Use the Docker service name 'redis'
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    
    # Caching Config
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300 
    
    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    
    # Stateless Git Engine Storage
    REPO_STORAGE_PATH = os.environ.get('REPO_STORAGE_PATH', '/tmp/coproof-storage')
    
    # GitHub OAuth
    GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID')
    GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET')
    GITHUB_OAUTH_SCOPES = "repo,read:user,user:email"

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    # For tests, we still connect to localhost because pytest runs on the host machine,
    # not inside the container.
    #temp used the dev db as test db, but in production should be a separate test db or an in-memory SQLite for speed.
    # All rows are droped at the end of each test function check conftest.     
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'postgresql://coproof:coproofpass@localhost:5432/coproof_test_db')
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = "NullCache" 

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False