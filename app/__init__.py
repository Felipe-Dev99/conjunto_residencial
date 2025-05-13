from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required
import os
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_mail import Mail
from dotenv import load_dotenv



# Cargar variables del archivo .env
load_dotenv()
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()



def create_app():
    app = Flask(__name__, template_folder='../views', static_folder='../static')

    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Para desarrollo, en producción usa caché


    print("Base de datos configurada:", app.config['SQLALCHEMY_DATABASE_URI'])
    # Configuración de Flask-Mail desde .env
    app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
    app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT"))
    app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS") == "True"
    app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
    app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")

    mail.init_app(app)
    
    app.config['META_ACCESS_TOKEN'] = os.getenv("META_ACCESS_TOKEN")
    app.config['META_WHATSAPP_PHONE_ID'] = os.getenv("META_WHATSAPP_PHONE_ID")
    app.config['TEMPLATE_NAME'] = os.getenv("TEMPLATE_NAME")

    # Clave secreta para manejar sesiones y seguridad
    app.config['SECRET_KEY'] = os.urandom(24)
    #app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY") # Genera una clave aleatoria
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)

    db.init_app(app)
    

    login_manager.init_app(app)
    login_manager.login_view = 'main.login'  # Ruta para login obligatorio

    from controllers.controller import main
    app.register_blueprint(main)

    from controllers.usuarios import usuarios_bp
    app.register_blueprint(usuarios_bp, url_prefix='/admin')

    from controllers.reserva import reserva_bp
    app.register_blueprint(reserva_bp, url_prefix='/reserva')

    from controllers.admin_reservas import admin_reservas_bp
    app.register_blueprint(admin_reservas_bp, url_prefix='/admin')

    from controllers.api_whatsapp import api_whatsapp
    app.register_blueprint(api_whatsapp)

    from controllers.api_mail import api_mail
    app.register_blueprint(api_mail, url_prefix='/api_mail')

    from controllers.pqrs import pqrs_bp
    app.register_blueprint(pqrs_bp, url_prefix='/pqrs')

    from controllers.admin_pqrs import admin_pqrs_bp
    app.register_blueprint(admin_pqrs_bp, url_prefix='/admin')

    from controllers.configuracion import config_bp
    app.register_blueprint(config_bp, url_prefix='/admin/configuracion')

    from controllers.log import log_bp
    app.register_blueprint(log_bp, url_prefix='/admin')

    from controllers.comprobantes import comprobantes_bp
    app.register_blueprint(comprobantes_bp, url_prefix='/admin')

    from controllers.admin_facturacion import admin_factura_bp
    app.register_blueprint(admin_factura_bp, url_prefix='/admin')

    from controllers.facturacion import factura_bp
    app.register_blueprint(factura_bp, url_prefix='/facturacion')

    from controllers.admin_reportes import reportes_bp
    app.register_blueprint(reportes_bp, url_prefix='/admin')

    from controllers.copia_db import copias_bp
    app.register_blueprint(copias_bp, url_prefix='/admin')


    #UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'comprobantes')
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static/comprobantes_reservas')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    from controllers.config_base import obtener_permisos_usuario
    @app.context_processor
    def inject_permisos():
        return dict(permisos_usuario=obtener_permisos_usuario())
    
    from models.datos_conjunto import DatosConjunto
    @app.context_processor
    def inject_datos_conjunto():
        datos = DatosConjunto.query.first()
        return dict(datos=datos)
    
    from controllers.admin_facturacion import generar_facturas_al_ingresar
    @app.before_request
    def generar_facturas():
        generar_facturas_al_ingresar()

    
    from controllers.copia_db import generar_copia_seguridad_unica
    @app.before_request
    def crear_copia_db():
        generar_copia_seguridad_unica()

    from controllers.admin_pqrs import validar_estado_pqrs
    @app.before_request
    def ejecutar_validacion_pqrs():
        validar_estado_pqrs()


    #with app.app_context():
     #   db.create_all()

    return app
