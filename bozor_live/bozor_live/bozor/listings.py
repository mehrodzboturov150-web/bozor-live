# Listings, automotive specifications, gallery, filters and favorites.
# API preserves legacy schema and URLs, optional vehicle data in linked table.
import sqlite3
from flask import Blueprint, jsonify, request, session
from .db import get_db
from .media import save_photo, remove_photo
from .utils import CATEGORIES, CITIES, auth_required, fail, get_int

bp = Blueprint('listings', __name__, url_prefix='/api')
CAR_FIELDS = ('brand', 'model', 'year', 'mileage', 'transmission', 'fuel',
              'drive', 'body', 'engine', 'color', 'steering', 'car_condition')
SELECT_CAR = ', '.join('c.'+c+' AS car_'+c for c in CAR_FIELDS)


def _payload(row):
    return dict(row) if row else None


def _listing_by_id(listing_id):
    return get_db().execute(f'''SELECT l.*, u.username AS seller,
       CASE WHEN f.user_id IS NULL THEN 0 ELSE 1 END AS favorite,
       {SELECT_CAR}
       FROM listings l JOIN users u ON l.owner_id=u.id
       LEFT JOIN favorites f ON f.listing_id=l.id AND f.user_id=?
       LEFT JOIN car_details c ON c.listing_id=l.id
       WHERE l.id=?''', (session.get('uid', -1), listing_id)).fetchone()


def _validate_form():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    category = request.form.get('category', '').strip()
    city = request.form.get('city', '').strip()
    try: price = int(request.form.get('price', ''))
    except (ValueError, TypeError): raise ValueError('Укажи цену в сомони')
    if not 3 <= len(title) <= 100: raise ValueError('Название: от 3 до 100 символов')
    if not 5 <= len(description) <= 3000: raise ValueError('Описание: от 5 до 3000 символов')
    if category not in CATEGORIES or city not in CITIES: raise ValueError('Выбери категорию и город из списка')
    if not 0 <= price <= 999999999: raise ValueError('Цена должна быть от 0 до 999 999 999 сомони')
    return title, category, city, price, description


def _car_data(category):
    if category != 'Автомобили': return None
    data = {field: request.form.get('car_'+field, '').strip()[:100]
            for field in CAR_FIELDS}
    for field in ('year','mileage'):
        raw=data[field]
        try: data[field]=int(raw) if raw else None
        except ValueError: raise ValueError('Год и пробег должны быть числами')
    if data['year'] is not None and not 1900 <= data['year'] <= 2027:
        raise ValueError('Проверь год выпуска автомобиля')
    if data['mileage'] is not None and not 0 <= data['mileage'] <= 3000000:
        raise ValueError('Проверь пробег автомобиля')
    return data


def _save_images():
    files=request.files.getlist('photos')
    legacy=request.files.get('photo')
    if legacy and legacy.filename: files.insert(0, legacy)
    files=[f for f in files if f and f.filename]
    if len(files)>6: raise ValueError('Максимум 6 фотографий')
    saved=[]
    try:
        for f in files: saved.append(save_photo(f))
        return saved
    except Exception:
        for p in saved: remove_photo(p)
        raise


def _store_car(db, listing_id, details):
    db.execute('DELETE FROM car_details WHERE listing_id=?', (listing_id,))
    if details is not None:
        values=[details[f] for f in CAR_FIELDS]
        db.execute('INSERT INTO car_details(listing_id,'+','.join(CAR_FIELDS)+') VALUES ('+
                   ','.join('?' for _ in range(len(CAR_FIELDS)+1))+')', [listing_id]+values)


def _gallery(db, listing_id, fallback):
    photos=[r['url'] for r in db.execute('SELECT url FROM listing_photos WHERE listing_id=? ORDER BY position,id', (listing_id,))]
    return photos if photos else ([fallback] if fallback else [])


@bp.get('/listings')
def list_listings():
    query=request.args.get('q','').strip()[:100]
    category=request.args.get('category','')
    city=request.args.get('city','')
    mine=request.args.get('mine')=='1'
    favorites=request.args.get('favorites')=='1'
    page=get_int(request.args.get('page',1),default=1,low=1,high=10000)
    sort=request.args.get('sort','newest')
    where=['1=1']; args=[session.get('uid',-1)]
    if query:
        where.append('(l.title LIKE ? OR l.description LIKE ? OR c.brand LIKE ? OR c.model LIKE ?)')
        args += [f'%{query}%']*4
    if category in CATEGORIES:
        where.append('l.category=?');args.append(category)
    if city in CITIES:
        where.append('l.city=?');args.append(city)
    if mine:
        where.append('l.owner_id=?');args.append(session.get('uid',-1))
    if favorites: where.append('f.user_id IS NOT NULL')
    for arg, column in [('min_price','l.price'),('max_price','l.price'),('year_from','c.year'),
                        ('year_to','c.year'),('mileage_max','c.mileage')]:
        raw=request.args.get(arg)
        if raw not in (None,''):
            operation='<=' if arg in ('max_price','year_to','mileage_max') else '>='
            where.append(column+' '+operation+' ?'); args.append(get_int(raw, default=0,low=0,high=999999999))
    for arg,column in [('brand','c.brand'),('model','c.model'),('transmission','c.transmission'),('fuel','c.fuel')]:
        value=request.args.get(arg,'').strip()[:100]
        if value: where.append(column+'=?');args.append(value)
    ordering={'newest':'l.id DESC','oldest':'l.id ASC','price_asc':'l.price ASC,l.id DESC',
              'price_desc':'l.price DESC,l.id DESC'}.get(sort,'l.id DESC')
    from_sql='''FROM listings l JOIN users u ON u.id=l.owner_id
        LEFT JOIN favorites f ON f.listing_id=l.id AND f.user_id=?
        LEFT JOIN car_details c ON c.listing_id=l.id WHERE '''+' AND '.join(where)
    db=get_db()
    total=db.execute('SELECT COUNT(*) '+from_sql,args).fetchone()[0]
    per_page=24
    rows=db.execute(f'''SELECT l.*,u.username AS seller,
        CASE WHEN f.user_id IS NULL THEN 0 ELSE 1 END AS favorite,
        {SELECT_CAR} '''+from_sql+' ORDER BY '+ordering+' LIMIT ? OFFSET ?',
        args+[per_page,(page-1)*per_page]).fetchall()
    return jsonify(items=[_payload(r) for r in rows],total=total,page=page,
                   pages=max(1,(total+per_page-1)//per_page))


@bp.get('/listings/<int:listing_id>')
def get_listing(listing_id):
    row=_listing_by_id(listing_id)
    if not row: return fail('Объявление не найдено',404)
    x=_payload(row)
    x['photos']=_gallery(get_db(),listing_id,x['photo'])
    return jsonify(item=x)


@bp.post('/listings')
@auth_required
def create_listing():
    saved=[]
    try:
        title,category,city,price,description=_validate_form()
        car=_car_data(category)
        saved=_save_images()
        db=get_db()
        with db:
            cursor=db.execute('''INSERT INTO listings(owner_id,title,category,city,price,description,photo)
              VALUES(?,?,?,?,?,?,?)''',(session['uid'],title,category,city,price,description,saved[0] if saved else None))
            ident=cursor.lastrowid
            _store_car(db,ident,car)
            for pos,url in enumerate(saved):
                db.execute('INSERT INTO listing_photos(listing_id,url,position) VALUES(?,?,?)',(ident,url,pos))
        return jsonify(id=ident),201
    except ValueError as ex: return fail(str(ex))
    except Exception:
        for p in saved: remove_photo(p)
        raise


@bp.patch('/listings/<int:listing_id>')
@auth_required
def edit_listing(listing_id):
    db=get_db()
    old=db.execute('SELECT * FROM listings WHERE id=?',(listing_id,)).fetchone()
    if not old: return fail('Объявление не найдено',404)
    if old['owner_id']!=session['uid']: return fail('Нет доступа',403)
    saved=[]
    committed=False
    try:
        title,category,city,price,description=_validate_form()
        car=_car_data(category)
        saved=_save_images()
        old_photos=_gallery(db,listing_id,old['photo'])
        discard=request.form.get('remove_photo')=='1'
        photos=([] if discard else old_photos)+saved
        if len(photos)>6: return fail('Максимум 6 фотографий. Удали прежние перед добавлением новых.')
        with db:
            db.execute('''UPDATE listings SET title=?,category=?,city=?,price=?,description=?,photo=?
               WHERE id=? AND owner_id=?''',(title,category,city,price,description,photos[0] if photos else None,listing_id,session['uid']))
            _store_car(db,listing_id,car)
            db.execute('DELETE FROM listing_photos WHERE listing_id=?',(listing_id,))
            for pos,url in enumerate(photos):
                db.execute('INSERT INTO listing_photos(listing_id,url,position) VALUES(?,?,?)',(listing_id,url,pos))
        committed=True
        if discard:
            for p in old_photos: remove_photo(p)
        return jsonify(ok=True,id=listing_id)
    except ValueError as ex: return fail(str(ex))
    finally:
        # Remove staged images when validation or transaction fails.
        if saved and not committed:
            for p in saved: remove_photo(p)


@bp.delete('/listings/<int:listing_id>')
@auth_required
def delete_listing(listing_id):
    db=get_db()
    row=db.execute('SELECT owner_id,photo FROM listings WHERE id=?',(listing_id,)).fetchone()
    if not row: return fail('Объявление не найдено',404)
    if row['owner_id']!=session['uid']: return fail('Нет доступа',403)
    photos=_gallery(db,listing_id,row['photo'])
    with db: db.execute('DELETE FROM listings WHERE id=?',(listing_id,))
    for p in photos: remove_photo(p)
    return jsonify(ok=True)


@bp.post('/favorites/<int:listing_id>')
@auth_required
def toggle_favorite(listing_id):
    db=get_db()
    if not db.execute('SELECT id FROM listings WHERE id=?',(listing_id,)).fetchone():
        return fail('Объявление не найдено',404)
    current=db.execute('SELECT 1 FROM favorites WHERE user_id=? AND listing_id=?',
                       (session['uid'],listing_id)).fetchone()
    with db:
        if current: db.execute('DELETE FROM favorites WHERE user_id=? AND listing_id=?',(session['uid'],listing_id))
        else: db.execute('INSERT INTO favorites(user_id,listing_id) VALUES(?,?)',(session['uid'],listing_id))
    return jsonify(favorite=not bool(current))
