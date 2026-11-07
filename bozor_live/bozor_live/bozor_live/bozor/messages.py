"""Private buyer/seller conversations attached to existing listings."""
from flask import Blueprint, jsonify, request, session
from .db import get_db
from .utils import auth_required, fail, get_int

bp = Blueprint('messages', __name__, url_prefix='/api')


def partner_for(listing_id, asked_partner=None):
    db = get_db()
    listing = db.execute('SELECT owner_id FROM listings WHERE id=?', (listing_id,)).fetchone()
    if listing is None:
        return None, fail('Объявление не найдено', 404)
    me = session['uid']
    if listing['owner_id'] != me:
        return listing['owner_id'], None
    partner = get_int(asked_partner, low=1)
    if not partner or partner == me:
        return None, fail('Выбери собеседника из списка чатов')
    # Sellers may only reply to users who previously contacted them about the listing.
    found = db.execute('''SELECT 1 FROM messages WHERE listing_id=? AND
        ((sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?)) LIMIT 1''',
        (listing_id, partner, me, me, partner)).fetchone()
    if not found:
        return None, fail('Собеседник не найден', 403)
    return partner, None


@bp.get('/messages/<int:listing_id>')
@auth_required
def get_messages(listing_id):
    partner, problem = partner_for(listing_id, request.args.get('partner'))
    if problem:
        return problem
    me = session['uid']
    rows = get_db().execute('''SELECT m.*,u.username AS sender
      FROM messages m JOIN users u ON m.sender_id=u.id
      WHERE m.listing_id=? AND
      ((m.sender_id=? AND m.recipient_id=?) OR (m.sender_id=? AND m.recipient_id=?))
      ORDER BY m.id ASC LIMIT 200''', (listing_id, me, partner, partner, me)).fetchall()
    return jsonify(items=[dict(r) for r in rows], partner=partner)


@bp.post('/messages/<int:listing_id>')
@auth_required
def send_message(listing_id):
    data = request.get_json(silent=True) or {}
    body = str(data.get('body', '')).strip()
    if not 1 <= len(body) <= 1000:
        return fail('Длина сообщения должна быть от 1 до 1000 символов')
    partner, problem = partner_for(listing_id, data.get('partner'))
    if problem:
        return problem
    if partner == session['uid']:
        return fail('Нельзя написать самому себе')
    db = get_db()
    if not db.execute('SELECT id FROM users WHERE id=?', (partner,)).fetchone():
        return fail('Собеседник не найден', 404)
    db.execute('INSERT INTO messages(listing_id,sender_id,recipient_id,body) VALUES(?,?,?,?)',
               (listing_id, session['uid'], partner, body))
    db.commit()
    return jsonify(ok=True), 201


@bp.get('/conversations')
@auth_required
def conversations():
    me = session['uid']
    rows = get_db().execute('''SELECT l.id AS listing_id, l.title,
      u.id AS partner_id, u.username AS partner, MAX(m.id) AS last_message_id
      FROM messages m JOIN listings l ON l.id=m.listing_id
      JOIN users u ON u.id=CASE WHEN m.sender_id=? THEN m.recipient_id ELSE m.sender_id END
      WHERE m.sender_id=? OR m.recipient_id=?
      GROUP BY l.id,u.id ORDER BY last_message_id DESC LIMIT 100''', (me, me, me)).fetchall()
    return jsonify(items=[dict(r) for r in rows])
