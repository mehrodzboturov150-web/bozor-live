"""Smoke tests for the redesigned API and legacy data compatibility."""
import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from bozor import create_app


class MarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.app = create_app({'TESTING':True, 'SECRET_KEY':'test-only-key',
                               'DATABASE_PATH':str(root/'bozor.db'),
                               'UPLOAD_DIR':str(root/'uploads'),
                               'SESSION_COOKIE_SECURE':False})
        self.client=self.app.test_client()
        self.csrf=self.client.get('/api/me').json['csrf']

    def tearDown(self):
        self.temp.cleanup()

    def write(self, method, path, **kwargs):
        headers=kwargs.pop('headers',{})
        headers['X-CSRF-Token']=self.csrf
        return self.client.open(path,method=method,headers=headers,**kwargs)

    def register(self, username='seller'):
        response=self.write('POST','/api/register',json={'username':username,'password':'testpassword123'})
        self.assertEqual(response.status_code,201,response.json)
        return response.json

    def test_legacy_schema_and_car_tables(self):
        with self.app.app_context():
            from bozor.db import get_db
            db=get_db()
            for table in ('users','listings','favorites','messages','car_details','listing_photos'):
                self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())

    def test_new_listing_and_vehicle_filters(self):
        self.register()
        form={'title':'Toyota Camry, 2018','category':'Автомобили','city':'Худжанд',
              'price':'150000','description':'Проверка тестового автомобиля',
              'car_brand':'Toyota','car_model':'Camry','car_year':'2018',
              'car_mileage':'84000','car_transmission':'Автомат','car_fuel':'Бензин'}
        r=self.write('POST','/api/listings',data=form)
        self.assertEqual(r.status_code,201,r.json)
        item=self.client.get('/api/listings/'+str(r.json['id'])).json['item']
        self.assertEqual(item['car_brand'],'Toyota')
        self.assertEqual(item['car_year'],2018)
        self.assertEqual(item['photos'],[])
        self.assertEqual(self.client.get('/api/listings?category=Автомобили&brand=Toyota&year_from=2017').json['total'],1)
        self.assertEqual(self.client.get('/api/listings?category=Автомобили&brand=Honda').json['total'],0)
        self.assertEqual(self.client.get('/listing/'+str(r.json['id'])).status_code,200)
        self.assertEqual(self.write('POST','/api/favorites/'+str(r.json['id'])).status_code,200)

    def test_gallery_and_edit(self):
        self.register()
        buffer=io.BytesIO()
        Image.new('RGB',(50,40),(50,80,100)).save(buffer,format='PNG')
        buffer.seek(0)
        form={'title':'BMW 320','category':'Автомобили','city':'Душанбе',
              'price':'90000','description':'Автомобиль для тестирования',
              'car_brand':'BMW','car_model':'320','car_year':'2015',
              'photos':(buffer,'car.png')}
        r=self.write('POST','/api/listings',data=form,content_type='multipart/form-data')
        self.assertEqual(r.status_code,201,r.json)
        ident=r.json['id']
        item=self.client.get('/api/listings/'+str(ident)).json['item']
        self.assertEqual(len(item['photos']),1)
        self.assertEqual(self.client.get(item['photos'][0]).status_code,200)
        form.pop('photos')
        form['price']='85000'
        changed=self.write('PATCH','/api/listings/'+str(ident),data=form)
        self.assertEqual(changed.status_code,200,changed.json)
        self.assertEqual(self.client.get('/api/listings/'+str(ident)).json['item']['price'],85000)
        self.assertEqual(self.write('DELETE','/api/listings/'+str(ident)).status_code,200)
        self.assertEqual(self.client.get('/api/listings/'+str(ident)).status_code,404)

    def test_post_requires_csrf(self):
        r=self.client.post('/api/register',json={'username':'example','password':'testpassword123'})
        self.assertEqual(r.status_code,403)


if __name__=='__main__':
    unittest.main()
