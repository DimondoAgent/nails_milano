"""
Запусти этот скрипт внутри контейнера:
  docker cp reset_password.py nails_milano:/app/reset_password.py
  docker exec -it nails_milano python3 reset_password.py
"""
import os, sys

# Нужен SECRET_KEY чтобы импортировать app
if not os.environ.get('SECRET_KEY'):
    print("ERROR: SECRET_KEY не задан. Запускай внутри контейнера, где есть .env")
    sys.exit(1)

from app import app, db, Admin

NEW_PASSWORD = "y96geT9Q!"

with app.app_context():
    admin = Admin.query.first()
    if not admin:
        print("Админ не найден в БД!")
        sys.exit(1)
    admin.set_password(NEW_PASSWORD)
    db.session.commit()
    print(f"[OK] Пароль для '{admin.username}' успешно изменён.")
