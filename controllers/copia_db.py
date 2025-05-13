import os
import subprocess
from datetime import datetime, date
from flask import current_app, Blueprint, render_template, send_from_directory
from sqlalchemy.exc import SQLAlchemyError
from app import db
from models.CopiaSeguridad import CopiaSeguridad


copias_bp = Blueprint('copias', __name__)

@copias_bp.route('/copias')
def ver_copias():
    base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    ruta_copias = os.path.join(base_dir, 'static', 'copias')
    archivos = []
    for archivo in os.listdir(ruta_copias):
        if archivo.endswith('.sql') or archivo.endswith('.bak') or archivo.endswith('.zip'):
            ruta_archivo = os.path.join(ruta_copias, archivo)
            fecha_creacion = datetime.fromtimestamp(os.path.getctime(ruta_archivo)).strftime('%Y-%m-%d %H:%M:%S')
            archivos.append({'nombre': archivo, 'fecha': fecha_creacion})
    return render_template('copias_db/ver_copias.html', archivos=archivos)

@copias_bp.route('/copias/descargar/<nombre_archivo>')
def descargar_copia(nombre_archivo):
    base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    ruta_copias = os.path.join(base_dir, 'static', 'copias')
    return send_from_directory(ruta_copias, nombre_archivo, as_attachment=True)

def generar_copia_seguridad_unica():
    try:
        with current_app.app_context():
            hoy = date.today()
            copia_hoy = CopiaSeguridad.query.filter(db.func.date(CopiaSeguridad.fecha) == hoy).first()

            if copia_hoy:
                return

            usuario = 'root'
            contraseña = 'root'
            nombre_bd = 'conjunto_residencial'
            base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
            ruta_carpeta = os.path.join(base_dir, 'static', 'copias')
            os.makedirs(ruta_carpeta, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"backup_{timestamp}.sql"
            ruta_completa = os.path.join(ruta_carpeta, nombre_archivo)

            mysqldump_path = r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe'

            comando = [
                mysqldump_path,
                '-u', usuario,
                f'-p{contraseña}',
                nombre_bd
            ]

            with open(ruta_completa, 'w', encoding='utf-8') as archivo_salida:
                resultado = subprocess.run(comando, stdout=archivo_salida, stderr=subprocess.PIPE, text=True)

            estado = 'Exitoso' if resultado.returncode == 0 else 'Fallido'
            tamaño = os.path.getsize(ruta_completa) if resultado.returncode == 0 else 0

            nueva_copia = CopiaSeguridad(
                fecha=datetime.now(),
                ruta_archivo=ruta_completa,
                tamaño=tamaño,
                estado=estado
            )

            db.session.add(nueva_copia)
            db.session.commit()

    except Exception as e:
        print(f"Error en copia de seguridad: {e}")
