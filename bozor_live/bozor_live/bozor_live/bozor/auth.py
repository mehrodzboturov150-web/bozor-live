"""Account and session endpoints; existing username/password schema retained."""
import secrets
import sqlite3
from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_db
from .utils import fail

bp = Blueprint('auth', __name__, url_prefix='/api')


@bp.get('/me')
def me():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    user = {'id': session['uid'], 'username': session['username']} if session.get('uid') else None
    return jsonify(user=user, csrf=session['_csrf'])


@bp.post('/register')
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', ''))
    if not 3 <= len(username) <= 40 or not 8 <= len(password) <= 128:
        return fail('Имя: 3–40 символов; пароль: 8–128 символов')
    if any(c in username for c in '<>\r\n\t'):
        return fail('В имени есть недопустимые символы')
    try:
        db = get_db()
        cur = db.execute('INSERT INTO users(username,password) VALUES(?,?)',
                         (username, generate_password_hash(password)))
        db.commit()
    except sqlite3.IntegrityError:
        return fail('Это имя уже занято', 409)
    csrf = session.get('_csrf') or secrets.token_urlsafe(32)
    session.clear()
    session.permanent = True
    session.update(uid=cur.lastrowid, username=username, _csrf=csrf)
    return jsonify(user={'id': cur.lastrowid, 'username': username}, csrf=csrf), 201


@bp.post('/login')
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', ''))
    row = get_db().execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if row is None or not check_password_hash(row['password'], password):
        return fail('Неверное имя пользователя или пароль', 401)
    csrf = session.get('_csrf') or secrets.token_urlsafe(32)
    session.clear()
    session.permanent = True
    session.update(uid=row['id'], username=row['username'], _csrf=csrf)
    return jsonify(user={'id': row['id'], 'username': row['username']}, csrf=csrf)


@bp.post('/logout')
def logout():
    csrf = secrets.token_urlsafe(32)
    session.clear()
    session['_csrf'] = csrf
    return jsonify(ok=True, csrf=csrf)
