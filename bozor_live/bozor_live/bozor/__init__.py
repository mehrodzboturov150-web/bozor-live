"""Flask application factory for Bozor.tj."""
import logging
import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session

from .db import close_db, init_db


def create_app(test_config=None):
    root = Path(__file__).resolve().parent.parent
    app = Flask(__name__, template_folder=str(root / 'templates'), static_folder=str(root / 'static'))
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY') or secrets.token_hex(32),
        DATABASE_PATH=os.getenv('DATABASE_PATH', str(root / 'bozor.db')),
        UPLOAD_DIR=os.getenv('UPLOAD_DIR', str(root / 'static' / 'uploads')),
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,
        MAX_IMAGE_BYTES=5 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('RENDER', '').lower() == 'true' or os.getenv('COOKIE_SECURE') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        JSON_AS_ASCII=False,
    )
    if test_config:
        app.config.update(test_config)
    if not os.getenv('SECRET_KEY') and not app.config.get('TESTING'):
        app.logger.warning('SECRET_KEY is not set: existing sessions expire on server restart.')

    Path(app.config['DATABASE_PATH']).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config['UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    from .auth import bp as auth_bp
    from .listings import bp as listing_bp
    from .messages import bp as messages_bp
    from .media import bp as media_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(listing_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(media_bp)

    @app.get('/')
    @app.get('/listing/<int:listing_id>')
    def index(listing_id=None):
        return render_template('index.html')

    @app.get('/health')
    def health():
        return jsonify(status='ok')

    @app.before_request
    def protect_writes():
        """Simple session-bound CSRF token for all state-changing JSON/form APIs."""
        if request.path.startswith('/api/') and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            from hmac import compare_digest
            token = request.headers.get('X-CSRF-Token', '')
            expected = session.get('_csrf', '')
            if not token or not expected or not compare_digest(token, expected):
                return jsonify(error='Сессия устарела. Обновите страницу и попробуйте снова.'), 403

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error='Файл слишком большой. Максимальный размер фотографии — 5 МБ.'), 413

    return app
