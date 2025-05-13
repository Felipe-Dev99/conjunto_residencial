from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_login import login_required
from twilio.rest import Client
import random
import requests
from app import db
from models.usuario import Usuarios
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time, timedelta
from controllers.configuracion import require_permission

api_whatsapp = Blueprint('api_whatsapp', __name__)
# Cargar variables de entorno
load_dotenv()

# Configuración de Meta API
ACCESS_TOKEN = "EACJ5OR1KubsBOyZC6VKJm9WDIq9KeZBKd6gmbiVzsRgrvUbs13i6IZAZBXhROi2zzdZBZCZBseo48ovhrAJyXRkUISV7ssCByIucAaRVoaSvUSYTVZA6ZBSnmgxcr6dw59Ul2tctxy3hwOWf5ZAW73auZCMwyZBtb63wC7ORDqiYUGufZBZASTMPrY2EOtT4TjafBGZBzRcfHLOytC2YNu2gYE9TNBi8alpdioZD"
PHONE_NUMBER_ID = "588328477704377"
TEMPLATE_NAME = "codigo_recuperacion"

@api_whatsapp.route("/enviar_numero/<int:id>", methods=["GET", "POST"])
@require_permission('Administrar Usuarios')
@login_required
def enviar_numero(id):
    usuario = Usuarios.query.get_or_404(id)
    numero_destino = usuario.telefono

    if not numero_destino:
        flash("Número de destino requerido.", "danger")
        return redirect(url_for("usuarios.listar_usuarios"))

    # Generar código aleatorio
    numero_aleatorio = random.randint(1000, 9999)
   

    # URL de la API de Meta
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    # Configurar encabezados de autenticación
    headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
    }

    data = {
    "messaging_product": "whatsapp",
        "to": f"57{numero_destino}",  # Formato internacional
        "type": "template",
            "template": {
                "name": TEMPLATE_NAME,
                "language": {"code": "es"},
                "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(numero_aleatorio)}]
                },
                {
                "type": "button",
                "sub_type": "url",
                "index": 0,
                "parameters": [
                    {"type": "text", "text":  str(numero_aleatorio)}  # El código que el usuario copiará
                ]
            }
            ]
        }
    }

    try:
        # Enviar solicitud a la API de Meta
        #response = requests.post(url, json=data, headers=headers)
        response = requests.post(
        f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
        headers=headers,
        json=data
    )
        response_data = response.json()

        if response.status_code == 200:
            # Guardar el código temporal en la base de datos
            usuario.codigo_temporal = generate_password_hash(str(numero_aleatorio))
            usuario.fecha_temporal = datetime.now() + timedelta(days=2)  # Fecha actual + 2 días
            db.session.commit()

            flash("Código enviado correctamente vía WhatsApp.", "success")
            return redirect(url_for('main.login'))
        else:
            flash(f"Error de Meta: {response_data}", "danger")

    except Exception as e:
        flash(f"Error al enviar el código: {str(e)}", "danger")

    return redirect(url_for("usuarios.listar_usuarios"))

@api_whatsapp.route("/request_reset", methods=["GET", "POST"])
def request_reset():

    if request.method == 'POST':
        email = request.form.get('email')
        usuario = Usuarios.query.filter_by(email=email).first()
        

        if not usuario:
            flash("Usuario No Existe.", "danger")
            
        numero_destino = usuario.telefono
        numero_aleatorio = random.randint(1000, 9999)  # Genera número aleatorio

        # URL de la API de Meta
        url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

        # Configurar encabezados de autenticación
        headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
        }

        data = {
        "messaging_product": "whatsapp",
            "to": f"57{numero_destino}",  # Formato internacional
            "type": "template",
                "template": {
                    "name": TEMPLATE_NAME,
                    "language": {"code": "es"},
                    "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": str(numero_aleatorio)}]
                    },
                    {
                    "type": "button",
                    "sub_type": "url",
                    "index": 0,
                    "parameters": [
                        {"type": "text", "text":  str(numero_aleatorio)}  # El código que el usuario copiará
                    ]
                }
                ]
            }
        }

        try:
            # Enviar solicitud a la API de Meta
            #response = requests.post(url, json=data, headers=headers)
            response = requests.post(
            f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
            headers=headers,
            json=data
        )
            response_data = response.json()

            if response.status_code == 200:
                # Guardar el código temporal en la base de datos
                usuario.codigo_temporal = generate_password_hash(str(numero_aleatorio))
                usuario.fecha_temporal = datetime.now() + timedelta(days=2)  # Fecha actual + 2 días
                db.session.commit()

                flash("Código enviado correctamente vía WhatsApp.", "success")
                return redirect(url_for('main.login'))
            else:
                flash(f"Error de Meta: {response_data}", "danger")

        except Exception as e:
            flash(f"Error al enviar el código: {str(e)}", "danger")
            return redirect(url_for('main.login'))
    return render_template('auth/request_reset.html')
    #return {"message": "Número enviado correctamente", "sid": mensaje.sid}

@api_whatsapp.route('/reset_password/<int:id>', methods=['GET', 'POST'])
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
                return redirect(url_for("api_whatsapp.reset_password", id=id))
            else:
                user.contraseña = generate_password_hash(password)
                db.session.commit()
                flash("Tu contraseña ha sido restablecida.", "success")
                return redirect(url_for('main.login'))  # Redirigir a la página de login
    except:
        flash("El codigo ha expirado o es inválido.", "danger")
        return redirect(url_for('api_whatsapp.request_reset'))
    #return render_template("reset_password.html", id=user.id)


@api_whatsapp.route('/view_reset_password/<int:id>')
def view_reset_password(id):
    return render_template('auth/reset_password.html',id=id)



