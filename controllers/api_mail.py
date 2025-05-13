from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_mail import Message
from flask_login import login_required
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from controllers.configuracion import require_permission
from app import db, mail
from models.usuario import Usuarios
import random

# Crear un Blueprint para manejar las rutas
api_mail = Blueprint('api_mail', __name__)

@api_mail.route('/enviar_codigo_admin/<int:id>', methods=['GET'])
@login_required
@require_permission('Administrar Usuarios')
def enviar_codigo_admin(id):
    

        usuario = Usuarios.query.get_or_404(id)
        
        if not usuario:
            flash("Usuario No Existe.", "danger")

        codigo = str(random.randint(100000, 999999))

        try:
            msg = Message("Clave Temporal de Acceso", recipients=[usuario.email])
            msg.body = f"""Hola {usuario.nombre},

Has solicitado una clave temporal para acceder al sistema del Conjunto Residencial El Dorado.
Tu clave temporal es: {codigo}

🔐 Por favor, utiliza esta clave para iniciar sesión en el sistema. Te recomendamos cambiarla una vez hayas ingresado correctamente.


Si no solicitaste esta clave, ignora este mensaje o comunícate con el administrador del sistema.

Saludos,
Equipo de Soporte
Conjunto Residencial Portal Del Tamarindo IV - El Dorado
"""
            msg.html = f"""
<!DOCTYPE html>
<html>
  <head>
    <style>
       body {{
        font-family: Arial, sans-serif;
        background-color: #f4f4f4;
        padding: 20px;
      }}
      .container {{
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        max-width: 500px;
        margin: auto;
      }}
      .logo {{
        text-align: center;
        margin-bottom: 20px;
      }}
      .logo img {{
        width: 120px;
        height: auto;
      }}
      .code {{
        background-color: #f1f1f1;
        border: 1px dashed #007bff;
        padding: 10px;
        font-size: 24px;
        text-align: center;
        margin: 20px 0;
        color: #007bff;
        border-radius: 5px;
      }}
      .button {{
        display: inline-block;
        padding: 12px 25px;
        background-color: #007bff;
        color: white;
        text-decoration: none;
        border-radius: 5px;
        font-weight: bold;
        margin-top: 20px;
      }}
      .footer {{
        font-size: 12px;
        color: #999;
        margin-top: 30px;
        text-align: center;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <div class="logo">
        <!--img src="https://drive.google.com/file/d/1QdNEwu_NQDh9WTY5JBBZ0um7mV0hPYCN/view?usp=sharing" alt="Logo Conjunto El Dorado"-->
      </div>
      <h2>Hola {usuario.nombre},</h2>
      <p>Has solicitado una <strong>clave temporal</strong> para ingresar al sistema del <strong>Conjunto Residencial Portal Del Tamarindo IV - El Dorado</strong>.</p>
      <p>Tu clave es:</p>
      <div class="code">{codigo}</div>
      <p>Por favor, úsala para iniciar sesión. Te recomendamos cambiarla inmediatamente después de ingresar.</p>
      <p>Si no solicitaste esta clave, puedes ignorar este mensaje o contactar con el administrador del sistema.</p>
      <div class="footer">
        © 2025 Conjunto Residencial Portal Del Tamarindo IV - El Dorado
      </div>
    </div>
  </body>
</html>
"""
            mail.send(msg)
            
            
            usuario.codigo_temporal = generate_password_hash(str(codigo))
            usuario.fecha_temporal = datetime.now() + timedelta(days=2)  # Fecha actual + 2 días
            db.session.commit()
            flash("✅ Correo de Restablecimiento enviado correctamente.", "success")
            return redirect(url_for('usuarios.listar_usuarios'))

        except Exception as e:
           #print(f"❌ Error al enviar correo: {e}")
            flash("Error al enviar el correo. Inténtalo de nuevo.", "danger")

        return redirect(url_for("usuarios.listar_usuarios"))



@api_mail.route('/enviarCodigo', methods=['GET', 'POST'])
def enviar_codigo():
    if request.method == "POST":
        correo = request.form["correo"]

        usuario = Usuarios.query.filter_by(email=correo).first()
        
        if not usuario:
            flash("Usuario No Existe.", "danger")

        codigo = str(random.randint(100000, 999999))

        try:
            msg = Message("🔐 Clave Temporal de Acceso", recipients=[usuario.email])
            msg.body = f"""Hola {usuario.nombre},

Has solicitado una clave temporal para acceder al sistema del Conjunto Residencial El Dorado.
Tu clave temporal es: {codigo}

🔐 Por favor, utiliza esta clave para iniciar sesión en el sistema. Te recomendamos cambiarla una vez hayas ingresado correctamente.


Si no solicitaste esta clave, ignora este mensaje o comunícate con el administrador del sistema.

Saludos,
Equipo de Soporte
Conjunto Residencial Portal Del Tamarindo IV - El Dorado
"""
            msg.html = f"""
<!DOCTYPE html>
<html>
  <head>
    <style>
       body {{
        font-family: Arial, sans-serif;
        background-color: #f4f4f4;
        padding: 20px;
      }}
      .container {{
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        max-width: 500px;
        margin: auto;
      }}
      .logo {{
        text-align: center;
        margin-bottom: 20px;
      }}
      .logo img {{
        width: 120px;
        height: auto;
      }}
      .code {{
        background-color: #f1f1f1;
        border: 1px dashed #007bff;
        padding: 10px;
        font-size: 24px;
        text-align: center;
        margin: 20px 0;
        color: #007bff;
        border-radius: 5px;
      }}
      .button {{
        display: inline-block;
        padding: 12px 25px;
        background-color: #007bff;
        color: white;
        text-decoration: none;
        border-radius: 5px;
        font-weight: bold;
        margin-top: 20px;
      }}
      .footer {{
        font-size: 12px;
        color: #999;
        margin-top: 30px;
        text-align: center;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <div class="logo">
        <!--img src="https://drive.google.com/file/d/1QdNEwu_NQDh9WTY5JBBZ0um7mV0hPYCN/view?usp=sharing" alt="Logo Conjunto El Dorado"-->
      </div>
      <h2>Hola {usuario.nombre},</h2>
      <p>Has solicitado una <strong>clave temporal</strong> para ingresar al sistema del <strong>Conjunto Residencial Portal Del Tamarindo IV - El Dorado</strong>.</p>
      <p>Tu clave es:</p>
      <div class="code">{codigo}</div>
      <p>Por favor, úsala para iniciar sesión. Te recomendamos cambiarla inmediatamente después de ingresar.</p>
      <p>Si no solicitaste esta clave, puedes ignorar este mensaje o contactar con el administrador del sistema.</p>
      <div class="footer">
        © 2025 Conjunto Residencial Portal Del Tamarindo IV - El Dorado
      </div>
    </div>
  </body>
</html>
"""
            mail.send(msg)
            
            
            

            usuario.codigo_temporal = generate_password_hash(str(codigo))
            usuario.fecha_temporal = datetime.now() + timedelta(days=2)  # Fecha actual + 2 días
            db.session.commit()
            flash("✅ Correo enviado correctamente.", "success")
            return redirect(url_for('main.login'))

        except Exception as e:
            print(f"❌ Error al enviar correo: {e}")
            flash("Error al enviar el correo. Inténtalo de nuevo.", "danger")

        return redirect(url_for("api_mail.enviar_codigo"))

    return render_template('auth/request_reset.html')


@api_mail.route('/reset_password/<int:id>', methods=['GET', 'POST'])
@login_required
def reset_password(id):
    try:
        if request.method == 'POST':
            #codigo = request.form.get('codigo')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            user = Usuarios.query.filter_by(id=id).first()

            #if user and check_password_hash(user.codigo_temporal, codigo):

            if password != confirm_password:
                flash("Las contraseñas no coinciden.", "danger")
                return redirect(url_for("api_mail.reset_password", id=id))
            else:
                user.contraseña = generate_password_hash(password)
                db.session.commit()
                flash("Tu contraseña ha sido restablecida.", "success")
                return redirect(url_for('main.login'))  # Redirigir a la página de login
    except:
        flash("El codigo ha expirado o es inválido.", "danger")
        return redirect(url_for('api_mail.enviar_codigo'))
    
    return render_template("auth/reset_password.html", id=id)

@api_mail.route('/view_reset_password/<int:id>')
def view_reset_password(id):
    return render_template('auth/reset_password.html',id=id)


def enviar_notificacion(destinatario, asunto, tipo_accion, datos):
    """
    Envía una notificación por correo usando plantilla HTML.
    
    :param destinatario: correo electrónico del destinatario
    :param asunto: asunto del correo
    :param tipo_accion: tipo de acción ('abono', 'pqrs', 'reserva', etc.)
    :param datos: diccionario con los datos que se mostrarán en el correo
    """
    try:
        html = render_template('emails/notificacion_base.html', tipo=tipo_accion, datos=datos)
        msg = Message(asunto, recipients=[destinatario], html=html)
        mail.send(msg)
    except:
        pass  # Ignora cualquier error al enviar el correo  

