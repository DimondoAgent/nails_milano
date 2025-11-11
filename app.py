# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FileField, PasswordField, SubmitField
from wtforms.validators import DataRequired, InputRequired, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from flask import jsonify
from datetime import datetime, timedelta, date , time

#conf
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "salon.db"
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/images')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_random_string_12345' # 👈 Обязательно смените это!
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, DB_NAME)}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Limit 16MB

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Пожалуйста, войдите, чтобы получить доступ к админ-панели."
login_manager.login_message_category = "error" 


#db model
class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)

class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.Integer) 
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    is_available = db.Column(db.Boolean, default=True)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100), nullable=False)
    client_phone = db.Column(db.String(20), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    service = db.relationship('Service', backref='appointments')

    def __repr__(self):
        return f'<Appointment {self.client_name} at {self.start_datetime}>'


class Gallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    image_filename = db.Column(db.String(100), nullable=False)

class Profile(db.Model):
    id = id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    image_filename = db.Column(db.String(100), nullable=False)

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))

#admin form with flask
class LoginForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired("Введите логин")])
    password = PasswordField("Пароль", validators=[DataRequired("Введите пароль")])
    submit = SubmitField("Войти")

class ServiceForm(FlaskForm):
    name = StringField("Название услуги", validators=[DataRequired()])
    price = IntegerField("Цена (в рублях)", validators=[InputRequired(), NumberRange(min=0)])
    description = StringField("Краткое описание (необязательно)")
    submit_service = SubmitField("Сохранить услугу")

class GalleryForm(FlaskForm):
    title = StringField("Название работы", validators=[DataRequired()])
    image = FileField("Фото", validators=[DataRequired("Выберите файл")])
    submit_gallery = SubmitField("Загрузить фото")


class ProfileForm(FlaskForm):
    title = StringField("Текущее фото", validators=[DataRequired()])
    image = FileField("Фото", validators=[DataRequired("Выберите файл")])
    submit_gallery = SubmitField("Загрузить фото")


#routes for pages

# public ones

@app.route('/api/get_slots')
def get_slots():
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({"error": "Дата не указана"}), 400
    
    try:
        selected_date = date.fromisoformat(date_str)
        day_of_week = selected_date.weekday()
    except ValueError:
        return jsonify({"error": "Неверный формат даты (YYYY-MM-DD)"}), 400

    
    availability = db.session.get(Availability, day_of_week + 1) # ID = day+1
    if not availability or not availability.is_available:
        return jsonify({"slots": []}) 

    
    available_slots = []
    service_duration = timedelta(hours=1) 
    
    current_time = datetime.combine(selected_date, availability.start_time)
    end_work_time = datetime.combine(selected_date, availability.end_time)

    
    appointments_on_day = Appointment.query.filter(
        db.func.date(Appointment.start_datetime) == selected_date
    ).all()
    
    booked_intervals = set()
    for appt in appointments_on_day:
        appt_end = appt.start_datetime + timedelta(minutes=60) 
        
        slot = appt.start_datetime
        while slot < appt_end:
             booked_intervals.add(slot.time())
             slot += timedelta(hours=1) 

    
    slot_time = current_time
    while slot_time + service_duration <= end_work_time:
        
        if slot_time.time() not in booked_intervals and slot_time > datetime.now():
            available_slots.append(slot_time.strftime('%H:%M'))
            
       
        slot_time += timedelta(hours=1) 
        
    return jsonify({"slots": available_slots})



@app.route('/api/book_slot', methods=['POST'])
def book_slot():
    data = request.json
    client_name = data.get('name')
    client_phone = data.get('phone')
    datetime_str = data.get('datetime') # YYYY-MM-DD HH:MM
    service_id_str = data.get('service_id')
    
    if not all([client_name, client_phone, datetime_str, service_id_str]):
         return jsonify({"error": "Не все данные предоставлены"}), 400
         
    try:
        start_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        service_id = int(service_id_str)
        service = db.session.get(Service, service_id)
        if not service:
             return jsonify({"error": "Услуга не найдена"}), 404

        
        existing_appointment = Appointment.query.filter_by(start_datetime=start_dt).first()
        if existing_appointment:
            return jsonify({"success": False, "message": "Извините, это время только что заняли. Выберите другое."}), 409 # Conflict

        
        day_of_week = start_dt.weekday()
        availability = db.session.get(Availability, day_of_week + 1)
        if not availability or not availability.is_available or \
           start_dt.time() < availability.start_time or \
           (start_dt + timedelta(hours=1)).time() > availability.end_time: 
            return jsonify({"success": False, "message": "Выбранное время находится вне рабочих часов."}), 400
        
        
        new_appointment = Appointment(
            client_name=client_name,
            client_phone=client_phone,
            service_id=service_id,
            start_datetime=start_dt,
            duration_minutes=60
        )
        db.session.add(new_appointment)
        db.session.commit()
        return jsonify({"success": True, "message": "Вы успешно записаны!"})

    except ValueError:
         return jsonify({"error": "Неверный формат данных"}), 400
    except Exception as e:
         db.session.rollback()
         print(f"Ошибка при бронировании: {e}") # Выводим ошибку в консоль сервера
         return jsonify({"error": "Внутренняя ошибка сервера при бронировании."}), 500

@app.route('/')
def index():
    latest_works = Gallery.query.order_by(Gallery.id.desc()).limit(3).all()
    return render_template('index.html', latest_works=latest_works)

@app.route('/services')
def services():
    all_services = Service.query.order_by(Service.price).all()
    return render_template('services.html', services=all_services)

@app.route('/gallery')
def gallery():
    all_works = Gallery.query.order_by(Gallery.id.desc()).all()
    return render_template('gallery.html', works=all_works)

@app.route('/booking')
def booking():
    all_services = Service.query.order_by(Service.name).all()
    return render_template('booking.html', services=all_services)


@app.route('/profile')
def profile():

    return render_template('profile.html') 

# admin

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin')) 
    
    form = LoginForm()
    if form.validate_on_submit():
        admin = Admin.query.filter_by(username=form.username.data).first()
        if admin and admin.check_password(form.password.data):
            login_user(admin)
            request.args.get('next') 
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin'))
        else:
            flash("Неверный логин или пароль", "error")
            
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Вы успешно вышли.", "success")
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    service_form = ServiceForm()
    gallery_form = GalleryForm()

    if request.method == 'POST':
        #adding services. logic
        if service_form.submit_service.data and service_form.validate():
            new_service = Service(
                name=service_form.name.data,
                price=service_form.price.data,
                description=service_form.description.data
            )
            db.session.add(new_service)
            db.session.commit()
            flash("Услуга успешно добавлена!", "success")
            return redirect(url_for('admin'))

        # adding photos. logic
        if gallery_form.submit_gallery.data and gallery_form.validate():
            file = gallery_form.image.data
            filename = secure_filename(file.filename)
            
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
                
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # cheching for non-repetion
            if os.path.exists(file_path):
                 flash(f"Файл с именем {filename} уже существует! Переименуйте файл и попробуйте снова.", "error")
                 return redirect(url_for('admin'))
                 
            file.save(file_path)
            
            new_work = Gallery(
                title=gallery_form.title.data,
                image_filename=filename
            )
            db.session.add(new_work)
            db.session.commit()
            flash("Фото успешно загружено!", "success")
            return redirect(url_for('admin'))

    # uploading data for admin (GET-request)
    all_services = Service.query.order_by(Service.name).all()
    all_works = Gallery.query.order_by(Gallery.id.desc()).all()

    today_start = datetime.combine(date.today(), time.min) 
    upcoming_appointments = Appointment.query.filter(Appointment.start_datetime >= today_start).order_by(Appointment.start_datetime).all()
    
    return render_template('admin.html', 
                           service_form=service_form, 
                           gallery_form=gallery_form,
                           services=all_services,
                           works=all_works, appointments=upcoming_appointments)

# delete logic
@app.route('/admin/delete_service/<int:service_id>', methods=['POST'])
@login_required
def delete_service(service_id):
    service_to_delete = db.session.get(Service, service_id)
    if service_to_delete:
        db.session.delete(service_to_delete)
        db.session.commit()
        flash("Услуга удалена.", "success")
    else:
        flash("Услуга не найдена.", "error")
    return redirect(url_for('admin'))

@app.route('/admin/delete_work/<int:work_id>', methods=['POST'])
@login_required
def delete_work(work_id):
    work_to_delete = db.session.get(Gallery, work_id)
    if work_to_delete:
        try:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], work_to_delete.image_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            else:
                flash(f"Файл {work_to_delete.image_filename} не найден на сервере.", "warning")
        except OSError as e:
            flash(f"Ошибка при удалении файла: {e}", "error")
            
        db.session.delete(work_to_delete)
        db.session.commit()
        flash("Работа удалена.", "success")
    else:
        flash("Работа не найдена.", "error")
    return redirect(url_for('admin'))

@app.route('/admin/delete_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def delete_appointment(appointment_id):
    appointment_to_delete = db.session.get(Appointment, appointment_id)
    if appointment_to_delete:
        #checking for an appointment
        if appointment_to_delete.start_datetime >= datetime.now():
             db.session.delete(appointment_to_delete)
             db.session.commit()
             flash("Запись успешно отменена.", "success")
        else:
             flash("Нельзя отменить прошедшую запись.", "warning")
    else:
        flash("Запись не найдена.", "error")
    return redirect(url_for('admin'))



# start
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        #admin creation
        if not Admin.query.first():
            print("Создание первого админа...")
            admin = Admin(username='master')
            admin.set_password('super1234') 
            db.session.add(admin)
            db.session.commit()
            print("Админ 'master' с паролем 'super1234' создан.")

        if not Availability.query.first():
             print("Заполнение базового расписания...")
             schedule = [
                 # Пн-Пт с 9 до 18, Сб-Вс выходной
                 {'day': 0, 'start': '09:00', 'end': '18:00', 'avail': True}, # Пн
                 {'day': 1, 'start': '09:00', 'end': '18:00', 'avail': True}, # Вт
                 {'day': 2, 'start': '09:00', 'end': '18:00', 'avail': True}, # Ср
                 {'day': 3, 'start': '09:00', 'end': '18:00', 'avail': True}, # Чт
                 {'day': 4, 'start': '09:00', 'end': '18:00', 'avail': True}, # Пт
                 {'day': 5, 'start': '00:00', 'end': '00:00', 'avail': False}, # Сб
                 {'day': 6, 'start': '00:00', 'end': '00:00', 'avail': False}  # Вс
             ]
             for item in schedule:
                 avail = Availability(
                     day_of_week=item['day'],
                     start_time=time.fromisoformat(item['start']),
                     end_time=time.fromisoformat(item['end']),
                     is_available=item['avail']
                 )
                 db.session.add(avail)
             db.session.commit()
             print("Базовое расписание создано.")
            
    app.run(debug=True)