import os
from flask import Blueprint, render_template, request, send_from_directory, flash, redirect, url_for, jsonify
from models.reserva import Reserva
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
from app import db
from controllers.log import registrar_log
from controllers.configuracion import require_permission

comprobantes_bp = Blueprint('comprobantes', __name__)

CARPETA_COMPROBANTES = os.path.join(os.getcwd(), 'static','comprobantes_reservas')
import os
from flask import render_template, request, send_from_directory, abort, url_for
from werkzeug.utils import secure_filename
from datetime import datetime

# Configuración
CARPETA_STATIC = os.path.join(os.getcwd(), 'static')  # Ruta absoluta a static
PAGE_SIZE = 20  # Resultados por página
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'docx', 'xlsx'}  # Extensiones permitidas (opcional)

@comprobantes_bp.route('/comprobantes', methods=['GET'])
@require_permission('Buscar Comprobantes')
def listar_comprobantes():
    # Parámetros de búsqueda
    nombre_archivo = request.args.get('nombre_archivo', '').strip()
    extension = request.args.get('extension', '').strip().lower()
    pagina = request.args.get('pagina', 1, type=int)

    # Validación de página
    if pagina < 1:
        pagina = 1

    archivos_encontrados = []
    
    # Búsqueda recursiva con seguridad
    for root, dirs, files in os.walk(CARPETA_STATIC):
        for file in files:
            file_path = os.path.join(root, file)
            
            # Verificación de seguridad
            if not os.path.abspath(file_path).startswith(CARPETA_STATIC):
                continue
            
            # Filtrar por nombre y extensión
            match_nombre = not nombre_archivo or nombre_archivo.lower() in file.lower()
            match_extension = not extension or file.lower().endswith(f'.{extension}')
            
            if match_nombre and match_extension:
                ruta_relativa = os.path.relpath(file_path, CARPETA_STATIC)
                archivos_encontrados.append({
                    'nombre': file,
                    'ruta': ruta_relativa,
                    'ruta_segura': url_for('comprobantes.serve_static', filename=ruta_relativa),
                    'directorio': os.path.dirname(ruta_relativa),
                    'tamaño': os.path.getsize(file_path),
                    'modificacion': datetime.fromtimestamp(os.path.getmtime(file_path)),
                    'extension': os.path.splitext(file)[1].lower()
                })

    # Ordenar por fecha de modificación (más reciente primero)
    archivos_encontrados.sort(key=lambda x: x['modificacion'], reverse=True)

    # Paginación
    total_archivos = len(archivos_encontrados)
    total_paginas = max(1, (total_archivos + PAGE_SIZE - 1) // PAGE_SIZE)
    archivos_paginados = archivos_encontrados[(pagina-1)*PAGE_SIZE : pagina*PAGE_SIZE]

    # Consulta original de comprobantes (opcional)
    comprobantes = Reserva.query.filter(Reserva.comprobante_pago.isnot(None)).limit(10)
    registrar_log(current_user.id,"Comprobantes", "Listar Comprobantes")

    return render_template(
        'comprobantes/listar_archivos.html',
        archivos=archivos_paginados,
        comprobantes=comprobantes,
        termino_busqueda=nombre_archivo,
        extension_busqueda=extension,
        paginacion={
            'pagina_actual': pagina,
            'total_paginas': total_paginas,
            'total_archivos': total_archivos
        },
        extensiones_permitidas=ALLOWED_EXTENSIONS
    )

@comprobantes_bp.route('/static/<path:filename>')
@require_permission('Buscar Comprobantes')
def serve_static(filename):
    """Endpoint seguro para servir archivos"""
    safe_path = os.path.join(CARPETA_STATIC, filename)
    
    # Validaciones de seguridad
    if not os.path.exists(safe_path):
        abort(404, description="Archivo no encontrado")
    if not os.path.isfile(safe_path):
        abort(403, description="Acceso no permitido")
    if not os.path.abspath(safe_path).startswith(CARPETA_STATIC):
        abort(403, description="Ruta no permitida")
    
    # Configurar para descarga o visualización
    as_attachment = request.args.get('download', '0') == '1'
    
    return send_from_directory(
        directory=os.path.dirname(safe_path),
        path=os.path.basename(safe_path),
        as_attachment=as_attachment,
        conditional=True  # Soporte para If-Modified-Since
    )

# Opcional: Endpoint alternativo para descargas directas
@comprobantes_bp.route('/descargar/<path:filename>')
@require_permission('Buscar Comprobantes')
def descargar_archivo(filename):
    """Endpoint exclusivo para descargas"""
    safe_path = os.path.join(CARPETA_STATIC, filename)
    
    if not os.path.abspath(safe_path).startswith(CARPETA_STATIC):
        abort(403)

    registrar_log(current_user.id,"Comprobantes", "Descarga Comprobantes")
    
    return send_from_directory(
        os.path.dirname(safe_path),
        os.path.basename(safe_path),
        as_attachment=True,
        download_name=os.path.basename(filename)  # Nombre sugerido para descarga
    )

@comprobantes_bp.route('/comprobantes/descargar/<path:comprobante_path>')
@require_permission('Buscar Comprobantes')
def descargar_comprobante(comprobante_path):
    comprobante = Reserva.query.filter_by(comprobante_path=comprobante_path).first()
    if not comprobante:
        flash("Archivo no encontrado.", "danger")
        return redirect(request.referrer or url_for('comprobantes.listar_comprobantes'))

    try:
        registrar_log(current_user.id,"Comprobantes", "Descarga Comprobantes")
        return send_from_directory(CARPETA_COMPROBANTES, comprobante_path, as_attachment=True, download_name=comprobante.comprobante_pago)
    except FileNotFoundError:
        flash("El archivo no existe en el servidor.", "danger")
        return redirect(request.referrer or url_for('comprobantes.listar_comprobantes'))
    
@comprobantes_bp.route('/comprobantes/buscar')
@require_permission('Buscar Comprobantes')
@login_required
def buscar_comprobantes():
    query = request.args.get('query', '').strip()
    
    # Filtrar solo los comprobantes que tienen un nombre de archivo válido
    comprobantes_query = Reserva.query.filter(Reserva.comprobante_pago.isnot(None))
    

    if query:
        comprobantes_query = comprobantes_query.filter(Reserva.comprobante_pago.ilike(f"%{query}%"))

    comprobantes = comprobantes_query.all()

    return jsonify([
        {"comprobante_pago": c.comprobante_pago, "comprobante_path": c.comprobante_path}
        for c in comprobantes
    ])