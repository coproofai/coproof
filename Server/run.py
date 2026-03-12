import os
from app import create_app, socketio
from config import DevelopmentConfig, TestingConfig

# Create the application instance using Development Config
app = create_app(config_class=DevelopmentConfig)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug_enabled = os.getenv('FLASK_DEBUG', '0') == '1'
    reloader_enabled = os.getenv('FLASK_USE_RELOADER', '0') == '1'
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=debug_enabled,
        use_reloader=reloader_enabled,
        allow_unsafe_werkzeug=True,
    )