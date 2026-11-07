"""Validated uploads stored separately from application source."""
import re
import uuid
from pathlib import Path
from flask import Blueprint, current_app, send_from_directory
from PIL import Image, ImageOps, UnidentifiedImageError

bp = Blueprint('media', __name__)
SAFE_NAME = re.compile(r'^[a-f0-9]{32}\.jpg$')
Image.MAX_IMAGE_PIXELS = 22_000_000


def save_photo(file):
    if file is None or not file.filename:
        return None
    try:
        # Check byte size even if request is chunked.
        file.stream.seek(0, 2)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > current_app.config['MAX_IMAGE_BYTES']:
            raise ValueError('Фотография должна быть меньше 5 МБ')
        with Image.open(file.stream) as original:
            original.verify()
        file.stream.seek(0)
        with Image.open(file.stream) as original:
            img = ImageOps.exif_transpose(original)
            img.thumbnail((1600, 1600))
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            elif img.mode == 'L':
                img = img.convert('RGB')
            name = uuid.uuid4().hex + '.jpg'
            target = Path(current_app.config['UPLOAD_DIR']) / name
            img.save(target, format='JPEG', quality=84, optimize=True)
            return '/media/' + name
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValueError('Не удалось прочитать фотографию. Используй JPG, PNG или WEBP до 5 МБ.') from exc


def remove_photo(path):
    if not path:
        return
    name = path.rsplit('/', 1)[-1]
    if not SAFE_NAME.fullmatch(name):
        return
    target = Path(current_app.config['UPLOAD_DIR']) / name
    try:
        target.unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning('Unable to remove uploaded image %s', name)


@bp.get('/media/<name>')
def serve_media(name):
    if not SAFE_NAME.fullmatch(name):
        from flask import abort
        abort(404)
    return send_from_directory(current_app.config['UPLOAD_DIR'], name, max_age=3600)
