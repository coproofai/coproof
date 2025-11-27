from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_marshmallow import Marshmallow
from flask_caching import Cache  # <-- IMPORT
from celery import Celery

# Database ORM
db = SQLAlchemy()

# Migrations
migrate = Migrate()

# Authentication
jwt = JWTManager()

# Object Serialization/Validation
ma = Marshmallow()

# Caching
cache = Cache()  

# Real-time WebSockets
socketio = SocketIO()

# Async Task Queue
celery = Celery()