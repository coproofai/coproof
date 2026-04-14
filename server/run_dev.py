import os

from app import create_app, socketio
from config import get_config_class


def build_app():
    """Build the Flask application using environment-driven configuration."""
    return create_app(config_class=get_config_class(default='development'))


app = build_app()


def run():
    """Run the development server with Socket.IO support."""
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


if __name__ == '__main__':
    run()