import os, sqlite3, secrets, uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

ROOT=os.path.dirname(os.path.abspath(__file__))
app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config.update(MAX_CONTENT_LENGTH=5*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
DB=os.environ.get('DATABASE_PATH',os.path.join(ROOT,'bozor.db'))
UPLOAD=os.environ.get('UPLOAD_DIR',os.path.join(ROOT,'static','uploads'))
os.makedirs(os.path.dirname(DB),exist_ok=True)
os.makedirs(UPLOAD,exist_ok=True)

def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE,password TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,category TEXT NOT NULL,city TEXT NOT NULL,price INTEGER NOT NULL,description TEXT NOT NULL,photo TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS favorites(user_id INTEGER REFERENCES users(id),listing_id INTEGER REFERENCES listings(id) ON DELETE CASCADE,PRIMARY KEY(user_id,listing_id));
  CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,listing_id INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,sender_id INTEGER NOT NULL REFERENCES users(id),recipient_id INTEGER NOT NULL REFERENCES users(id),body TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
init()

def auth(f):
 @wraps(f)
 def inner(*args,**kwargs):
  if not session.get('uid'):return jsonify(error='Сначала войдите в аккаунт'),401
  return f(*args,**kwargs)
 return inner

def error(msg,status=400):return jsonify(error=msg),status

def listing_row(row):return dict(row)

@app.get('/')
def home():return render_template('index.html')

@app.get('/api/me')
def me():return jsonify(user={'id':session['uid'],'username':session['username']} if session.get('uid') else None)

@app.post('/api/register')
def register():
 d=request.get_json(silent=True) or {};u=str(d.get('username','')).strip();p=str(d.get('password',''))
 if not 3<=len(u)<=40 or not 8<=len(p)<=128:return error('Имя: 3–40 символов; пароль: минимум 8 символов')
 try:
  with db() as c:
   cur=c.execute('INSERT INTO users(username,password) VALUES(?,?)',(u,generate_password_hash(p)));uid=cur.lastrowid
 except sqlite3.IntegrityError:return error('Это имя уже занято',409)
 session.clear();session.update(uid=uid,username=u)
 return jsonify(user={'id':uid,'username':u})

@app.post('/api/login')
def login():
 d=request.get_json(silent=True) or {}
 with db() as c:r=c.execute('SELECT * FROM users WHERE username=?',(str(d.get('username','')).strip(),)).fetchone()
 if not r or not check_password_hash(r['password'],str(d.get('password',''))):return error('Неверное имя или пароль',401)
 session.clear();session.update(uid=r['id'],username=r['username']);return jsonify(user={'id':r['id'],'username':r['username']})

@app.post('/api/logout')
def logout():session.clear();return jsonify(ok=True)

@app.get('/api/listings')
def listings():
 q=request.args.get('q','').strip()[:100];cat=request.args.get('category','');city=request.args.get('city','');mine=request.args.get('mine')=='1';fav=request.args.get('favorites')=='1'
 sql='''SELECT l.*,u.username AS seller, CASE WHEN f.user_id IS NULL THEN 0 ELSE 1 END AS favorite FROM listings l JOIN users u ON u.id=l.owner_id LEFT JOIN favorites f ON f.listing_id=l.id AND f.user_id=? WHERE 1=1''';args=[session.get('uid',-1)]
 if q:sql+=' AND (l.title LIKE ? OR l.description LIKE ?)';args.extend(['%'+q+'%']*2)
 if cat:sql+=' AND l.category=?';args.append(cat)
 if city:sql+=' AND l.city=?';args.append(city)
 if mine:sql+=' AND l.owner_id=?';args.append(session.get('uid',-1))
 if fav:sql+=' AND f.user_id IS NOT NULL'
 sql+=' ORDER BY l.id DESC LIMIT 200'
 with db() as c:rows=[listing_row(r) for r in c.execute(sql,args)]
 return jsonify(items=rows)

@app.post('/api/listings')
@auth
def add_listing():
 title=request.form.get('title','').strip();desc=request.form.get('description','').strip();cat=request.form.get('category','').strip();city=request.form.get('city','').strip()
 try:price=int(request.form.get('price',''))
 except ValueError:return error('Укажите правильную цену')
 if not (3<=len(title)<=100 and 5<=len(desc)<=3000 and cat and city and 0<=price<=999999999):return error('Проверьте поля объявления')
 photo=None;file=request.files.get('photo')
 if file and file.filename:
  from PIL import Image,UnidentifiedImageError
  try:
   im=Image.open(file.stream);im.verify();file.stream.seek(0);im=Image.open(file.stream);im.thumbnail((1200,1200));im=im.convert('RGB')
   name=uuid.uuid4().hex+'.jpg';im.save(os.path.join(UPLOAD,name),format='JPEG',quality=82);photo='/static/uploads/'+name
  except (UnidentifiedImageError,OSError,ValueError):return error('Неверный формат изображения')
 with db() as c:cur=c.execute('INSERT INTO listings(owner_id,title,category,city,price,description,photo) VALUES(?,?,?,?,?,?,?)',(session['uid'],title,cat,city,price,desc,photo));id=cur.lastrowid
 return jsonify(id=id),201

@app.delete('/api/listings/<int:id>')
@auth
def delete_listing(id):
 with db() as c:
  r=c.execute('SELECT owner_id,photo FROM listings WHERE id=?',(id,)).fetchone()
  if not r:return error('Объявление не найдено',404)
  if r['owner_id']!=session['uid']:return error('Нет доступа',403)
  c.execute('DELETE FROM listings WHERE id=?',(id,))
 if r['photo']:
  try:os.remove(os.path.join(UPLOAD,os.path.basename(r['photo'])))
  except OSError:pass
 return jsonify(ok=True)

@app.post('/api/favorites/<int:id>')
@auth
def favorite(id):
 with db() as c:
  if not c.execute('SELECT id FROM listings WHERE id=?',(id,)).fetchone():return error('Объявление не найдено',404)
  r=c.execute('SELECT 1 FROM favorites WHERE user_id=? AND listing_id=?',(session['uid'],id)).fetchone()
  if r:c.execute('DELETE FROM favorites WHERE user_id=? AND listing_id=?',(session['uid'],id))
  else:c.execute('INSERT INTO favorites(user_id,listing_id) VALUES(?,?)',(session['uid'],id))
 return jsonify(favorite=not bool(r))

@app.get('/api/messages/<int:id>')
@auth
def messages(id):
 with db() as c:
  l=c.execute('SELECT owner_id FROM listings WHERE id=?',(id,)).fetchone()
  if not l:return error('Объявление не найдено',404)
  partner=request.args.get('partner',type=int)
  if l['owner_id']==session['uid']:
   if not partner:return error('Укажите собеседника')
  else:partner=l['owner_id']
  rows=c.execute('''SELECT m.*,u.username sender FROM messages m JOIN users u ON u.id=m.sender_id WHERE listing_id=? AND ((sender_id=? AND recipient_id=?) OR (sender_id=? AND recipient_id=?)) ORDER BY m.id''',(id,session['uid'],partner,partner,session['uid'])).fetchall()
 return jsonify(items=[dict(r) for r in rows],partner=partner)

@app.post('/api/messages/<int:id>')
@auth
def send_message(id):
 d=request.get_json(silent=True) or {};body=str(d.get('body','')).strip()
 if not 1<=len(body)<=1000:return error('Сообщение должно содержать 1–1000 символов')
 with db() as c:
  l=c.execute('SELECT owner_id FROM listings WHERE id=?',(id,)).fetchone()
  if not l:return error('Объявление не найдено',404)
  partner=int(d.get('partner') or 0) if l['owner_id']==session['uid'] else l['owner_id']
  if not partner or partner==session['uid']:return error('Нельзя отправить сообщение себе')
  if l['owner_id']==session['uid'] and not c.execute('SELECT 1 FROM messages WHERE listing_id=? AND (sender_id=? OR recipient_id=?) AND (sender_id=? OR recipient_id=?)',(id,partner,partner,session['uid'],session['uid'])).fetchone():return error('Собеседник не найден',403)
  if not c.execute('SELECT id FROM users WHERE id=?',(partner,)).fetchone():return error('Пользователь не найден',404)
  c.execute('INSERT INTO messages(listing_id,sender_id,recipient_id,body) VALUES(?,?,?,?)',(id,session['uid'],partner,body))
 return jsonify(ok=True),201

@app.get('/api/conversations')
@auth
def conversations():
 with db() as c:
  rows=c.execute('''SELECT DISTINCT l.id listing_id,l.title,u.id partner_id,u.username partner FROM messages m JOIN listings l ON l.id=m.listing_id JOIN users u ON u.id=CASE WHEN m.sender_id=? THEN m.recipient_id ELSE m.sender_id END WHERE m.sender_id=? OR m.recipient_id=? ORDER BY l.id DESC''',(session['uid'],session['uid'],session['uid'])).fetchall()
 return jsonify(items=[dict(r) for r in rows])

@app.errorhandler(413)
def large(_):return error('Файл слишком большой (максимум 5 МБ)',413)

if __name__=='__main__':app.run(debug=os.environ.get('FLASK_DEBUG')=='1',host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
