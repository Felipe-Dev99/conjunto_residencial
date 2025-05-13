from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models.usuario import Usuarios
from models.roles import Roles
from models.casas import Casas, Apartamento, Torre
from app import db, login_manager
from datetime import timedelta
from datetime import datetime, time, timedelta
from models.datos_conjunto import DatosConjunto
from controllers.log import registrar_log
from controllers.admin_facturacion import generar_facturas_al_ingresar
from controllers.copia_db import generar_copia_seguridad_unica

main = Blueprint('main', __name__)

@login_manager.user_loader
def load_user(user_id):
    return Usuarios.query.get(int(user_id))
from functools import wraps


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('main.login'))

            #if current_user.is_authenticated or current_user.roles.nombre not in roles:
            if session.get('role') not in roles:
                flash('Acceso denegado.', 'danger')
                return redirect(url_for('main.no_autorizado'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@main.route('/')
def home():

    return render_template('auth/home.html')

@main.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
     
        try:
            from controllers.configuracion import require_permission
            require_permission('Crear Usuario')
            nombre = request.form['nombre']
            identificacion = request.form['identificacion']
            email = request.form['email']
            contraseña = request.form['password']
            id_rol = int(request.form['id_rol'])
            telefono= request.form['telefono']
            
                # Obtener la casa seleccionada según la torre y apartamento elegidos

            if id_rol == 1:
                id_torre = request.form.get('id_torre')
                id_apartamento = request.form.get('id_apartamento')

                casa = Casas.query.filter_by(id_torre=id_torre, id_apartamento=id_apartamento).first()
                
                if not casa:
                    #flash("No se encontró una casa con la torre y apartamento seleccionados.", "danger")
                    #return redirect(url_for('usuarios.editar_usuario', id=id)

                    # Crear la casa con los IDs de la torre y apartamento
                    nueva_casa = Casas(id_torre=id_torre, id_apartamento=id_apartamento)
                    db.session.add(nueva_casa)
                    db.session.commit()
                    registrar_log(current_user.id,"Registro", "Crea Nuevo torre con aparamento id"+ str(id_torre) + " numero: "+str(id_apartamento))
                    casa = nueva_casa

            # Verificar si el rol existe
            role = Roles.query.get(id_rol)
            if not role:
                flash('Rol no válido', 'danger')
                return redirect(url_for('main.register'))
                
            # Verificar si el usuario ya existe
            existing_user = Usuarios.query.filter_by(email=email).first()
            if existing_user:
                flash('El nombre de email ya está en uso', 'warning')
                return redirect(url_for('main.register'))    
            
            hashed_password = generate_password_hash(contraseña)
            if id_rol == 1:
                new_user = Usuarios(nombre=nombre, identificacion=identificacion, email=email, contraseña=hashed_password, telefono=telefono, id_rol=int(id_rol), id_casa=casa.id, estado=1 )
            else:
                new_user = Usuarios(nombre=nombre, identificacion=identificacion, email=email, contraseña=hashed_password, telefono=telefono, id_rol=id_rol, estado=1 )
            db.session.add(new_user)
            db.session.commit()
            registrar_log(current_user.id,"Registro", "Se crea Usuario id "+ str(nombre)+" correo "+str(email)+ " identificacion "+str(identificacion))  
            flash('Usuario registrado con éxito', 'success')
            return redirect(url_for('usuarios.listar_usuarios'))
        except Exception as e:
            db.session.rollback()  # Deshacer la transacción si ocurre un error
            print(f'Error en el registro: {str(e)}', 'danger')
        
    return render_template('auth/register.html', roles = Roles.query.filter(Roles.id != 99).all(), casas = Casas.query.all(), torres= Torre.query.all(), apartamentos = Apartamento.query.all())

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuarios.query.filter_by(email=username).first()
        hoy = datetime.now()

        if user:
            if user.estado != 1:
                flash('Usuario Bloqueado', 'danger')
            else:
                # Primero validar contraseña normal
                if check_password_hash(user.contraseña, password):
                    login_user(user)
                    registrar_log(current_user.id, "Login", "Inicia Sesion")
                    

                    user.codigo_temporal = None
                    user.fecha_temporal = None
                    db.session.commit()

                    session['username'] = username
                    session['role'] = user.rol.nombre
                    session.permanent = True
                    
                    next_page = request.args.get('next')
                    if next_page:
                        return redirect(next_page)
                    elif user.id_rol == 1:
                        return redirect(url_for('main.home_usuario'))
                    else:
                        return redirect(url_for('main.home_admin'))

                # Si falla la contraseña normal, intentamos con código temporal
                elif user.codigo_temporal and check_password_hash(user.codigo_temporal, password):
                    if hoy <= user.fecha_temporal:
                        login_user(user) 
                        registrar_log(user.id, "Login", "Inicia Sesion por Codigo Temporal")
                        return redirect(url_for('api_mail.reset_password', id=user.id))
                    else:
                        flash('El código temporal ha expirado', 'danger')

                else:
                    flash('Usuario o contraseña incorrectos', 'danger')

        else:
            flash('Usuario No existe', 'danger')

    return render_template('auth/login.html')



@main.route('/logout')
@login_required
def logout():
    registrar_log(current_user.id,"Cierra Sesion", "Cierra Sesion") 
    logout_user()
    return redirect(url_for('main.home'))

@main.route('/no_autorizado')
def no_autorizado():
    registrar_log(current_user.id,"No Autorizado", "Ingresa a lugar No permitido") 
    return render_template('no_autorizado.html', usuario=current_user.id), 403  # Código de estado HTTP 403 (Prohibido)

@main.route('/admin')
@login_required
def home_admin():
    registrar_log(current_user.id,"Home-Admin", "Ingresa a Home-Admin") 
    return render_template('auth/home_admin.html')

@main.route('/usuario')
@role_required('Residente')
@login_required
def home_usuario():
    registrar_log(current_user.id,"Home-Usuario", "Ingresa a Home-Usuario") 
    return render_template('auth/home_usuario.html')




