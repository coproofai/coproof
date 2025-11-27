import os
from app import create_app, socketio
from config import DevelopmentConfig, TestingConfig

# Create the application instance using Development Config
app = create_app(config_class=TestingConfig)

if __name__ == '__main__':
    # We use socketio.run instead of app.run to support WebSockets
    # debug=True enables auto-reloader
    port = int(os.getenv('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)