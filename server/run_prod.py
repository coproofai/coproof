import os

from app import create_app
from config import get_config_class


def build_app():
    """Build the WSGI application using environment-driven configuration."""
    return create_app(config_class=get_config_class(default='production'))


app = build_app()


def run():
    """Run the production entrypoint with Flask's built-in server when executed directly."""
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port)


if __name__ == '__main__':
    run()