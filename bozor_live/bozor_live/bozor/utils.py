"""Shared API validation, authentication and response helpers."""
from functools import wraps
from flask import jsonify, session

CATEGORIES = ('Телефоны', 'Автомобили', 'Недвижимость', 'Электроника', 'Мебель', 'Одежда', 'Работа', 'Услуги', 'Другое')
CITIES = ('Душанбе', 'Худжанд', 'Бохтар', 'Куляб', 'Истаравшан', 'Турсунзаде', 'Пенджикент', 'Исфара', 'Канибадам', 'Другой город')


def fail(message, status=400):
    return jsonify(error=message), status


def auth_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if not session.get('uid'):
            return fail('Сначала войдите в аккаунт', 401)
        return fn(*args, **kwargs)
    return inner


def get_int(value, default=0, low=0, high=999999999):
    try:
        out = int(value)
        if low <= out <= high:
            return out
    except (TypeError, ValueError, OverflowError):
        pass
    return default
