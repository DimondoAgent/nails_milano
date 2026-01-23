from app import app, db, Service, Gallery
with app.app_context():
    # Создаем услугу
    s1 = Service(name="Маникюр + Гель-лак", price=1500, description="Выравнивание, покрытие, дизайн 2 пальцев")
    # Создаем работу в галерее
    g1 = Gallery(title="Красный френч", image_filename="red_french.jpg")

    # Добавляем в "очередь"
    db.session.add(s1)
    db.session.add(g1)

    # Сохраняем изменения в БД
    db.session.commit()