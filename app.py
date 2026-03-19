import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, FileField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_babel import Babel, gettext as _

babel = Babel()

# --- КОНФИГУРАЦИЯ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "maele_fashion.db"
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/images')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///maele_fashion.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['LANGUAGES'] = ['en', 'ru', 'it']

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["2000 per day", "500 per hour"],
    storage_uri="memory://"
)

# --- МОДЕЛИ БАЗЫ ДАННЫХ ---
class Gallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.String(50), nullable=True)
    size = db.Column(db.String(50), nullable=True)
    image_filename = db.Column(db.String(100), nullable=False)
    is_sold_out = db.Column(db.Boolean, default=False)

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

def get_locale():
    return session.get('lang', 'ru')
babel.init_app(app, locale_selector=get_locale)

# --- ФОРМЫ ---
class LoginForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    submit = SubmitField("Войти")

class GalleryForm(FlaskForm):
    brand = StringField("Бренд", validators=[DataRequired()])
    title = StringField("Название", validators=[DataRequired()])
    price = StringField("Цена")
    size = StringField("Размер")
    image = FileField("Фото", validators=[DataRequired()])
    submit_gallery = SubmitField("Добавить")

# --- МАРШРУТЫ ---
@app.route('/')
def index():
    latest_works = Gallery.query.filter_by(is_sold_out=False).order_by(Gallery.id.desc()).limit(6).all()
    return render_template('index.html', latest_works=latest_works)

@app.route('/gallery')
def gallery():
    all_works = Gallery.query.order_by(Gallery.is_sold_out.asc(), Gallery.id.desc()).all()
    return render_template('gallery.html', works=all_works)

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/booking')
def booking():
    return render_template('booking.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.context_processor
def inject_gettext():
    return dict(_=_)

# --- АДМИН ПАНЕЛЬ ---
@app.route('/secret-management-zone-99', methods=['GET', 'POST'])
@login_required
def admin():
    gallery_form = GalleryForm()
    if gallery_form.validate_on_submit():
        file = gallery_form.image.data
        filename = secure_filename(file.filename)
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_item = Gallery(
            brand=gallery_form.brand.data,
            title=gallery_form.title.data,
            price=gallery_form.price.data,
            size=gallery_form.size.data,
            image_filename=filename,
            is_sold_out=False
        )
        db.session.add(new_item)
        db.session.commit()
        return redirect(url_for('admin'))

    all_works = Gallery.query.order_by(Gallery.id.desc()).all()
    return render_template('admin.html', gallery_form=gallery_form, works=all_works)

@app.route('/admin/toggle_status/<int:work_id>', methods=['POST'])
@login_required
def toggle_status(work_id):
    item = db.session.get(Gallery, work_id)
    if item:
        item.is_sold_out = not item.is_sold_out
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/admin/delete_work/<int:work_id>', methods=['POST'])
@login_required
def delete_work(work_id):
    item = db.session.get(Gallery, work_id)
    if item:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item.image_filename))
        except:
            pass
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        admin = Admin.query.filter_by(username=form.username.data).first()
        if admin and admin.check_password(form.password.data):
            login_user(admin)
            return redirect(url_for('admin'))
        flash("Ошибка входа", "error")
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- ЗАПУСК ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not Admin.query.first():
            admin = Admin(username='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("--- Admin Created: admin / admin123 ---")
    
    app.run(host="0.0.0.0", port=5001, debug=True)