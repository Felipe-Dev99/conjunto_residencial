from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, send_from_directory, current_app
from flask_login import login_required, current_user
from datetime import datetime
from werkzeug.utils import secure_filename
from app import db
from models.pqrs import PQRS, estados_pqrs, descripcion_pqrs, tipo_pqrs, generar_numero_radicado, HistorialPQRS, PQRSArchivo
from datetime import datetime, time, timedelta
from models.datos_conjunto import DatosConjunto
import io
import os
import uuid
from textwrap import wrap
from controllers.configuracion import require_permission
from controllers.log import registrar_log
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from controllers.api_mail import enviar_notificacion

pqrs_bp = Blueprint('pqrs', __name__)


@pqrs_bp.route('/')
@login_required
@require_permission('Residente')
def listar():
    registrar_log(current_user.id,"PQRS", "Lista Pqrs")
    """ Mostrar los pqrs del usuario."""
    #respuesta = PQRS.query.filter_by(id_usuario=current_user.id).all()
    page = request.args.get('page', 1, type=int)  # Obtiene el número de página de los parámetros de la URL
    respuesta = PQRS.query.filter_by(id_usuario=current_user.id).order_by(PQRS.fecha_creacion.desc()).paginate(page=page, per_page=5)  # Paginación de 5 elementos
   
    
    return render_template('pqrs/listar_pqrs.html', pqrs_list=respuesta)

@pqrs_bp.route('/ver/<int:id>', methods=['GET'])
@login_required
@require_permission('Residente')
def ver_pqrs(id):
    pqrs = PQRS.query.filter_by(id=id, id_usuario=current_user.id).first()

    if not pqrs:
        flash("No tienes permiso para ver esta PQRS o no existe.", "danger")
        return redirect(url_for('pqrs.listar_pqrs'))
    

    historial = HistorialPQRS.query.filter_by(id_pqrs=id).order_by(HistorialPQRS.fecha_respuesta.asc()).all()
    # Diccionario para traducir los estados
    ESTADOS = {
        "1": "Registrada",
        "2": "En Proceso",
        "3": "Finalizadas"
    }


    # Transformamos los datos para enviar nombres correctos al template
    historial_traducido = []
    for item in historial:
        historial_traducido.append({
            "id": item.id,
            "respuesta": item.respuesta,
            "fecha_respuesta": item.fecha_respuesta.strftime("%Y-%m-%d %H:%M:%S"),
            "estado_anterior": ESTADOS.get(item.estado_anterior, "Desconocido"),
            "estado_actual": ESTADOS.get(item.estado_actual, "Desconocido"),
        })

    registrar_log(current_user.id,"PQRS", "Visualiza Pqrs id "+str(pqrs.id))
    archivos = PQRSArchivo.query.filter_by(id_pqrs=id).all()
    return render_template('pqrs/ver_pqrs.html', pqrs=pqrs, historial=historial_traducido, archivos=archivos)


ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@pqrs_bp.route('/crear_pqrs', methods=['GET', 'POST'])
@login_required
@require_permission('Residente')
def crear_pqrs():
    if request.method == 'POST':
        id_tipo = request.form.get('id_tipo')  
        id_descricpion = request.form.get('id_descripcion')
        observacion = request.form.get('observacion')

        # Validaciones
        if not tipo_pqrs.query.get(id_tipo):
            flash('Error: Debe seleccionar un tipo de PQRS.', 'danger')
            return redirect(url_for('pqrs.crear_pqrs'))

        if not descripcion_pqrs.query.get(id_descricpion):
            flash('Error: Tipo de PQRS no válido.', 'danger')
            return redirect(url_for('pqrs.crear_pqrs'))

        hoy = datetime.today().date()
        fecha_maxx = hoy + timedelta(days=15)

        numero_radicado = generar_numero_radicado()

        nueva_pqrs = PQRS(
            id_usuario=current_user.id,
            numero_radicado=numero_radicado,
            tipo=id_descricpion,
            observacion=observacion,
            id_estado=1,
            id_tipo=id_tipo,
            fecha_max=fecha_maxx
        )

        db.session.add(nueva_pqrs)
        db.session.commit()

        datos = {
            'usuario': current_user.nombre,
            'radicado': nueva_pqrs.numero_radicado,
            'tipop': nueva_pqrs.tipo_p.nombre,
            'tipod': nueva_pqrs.tipo_d.tipo,
            'descripcion': nueva_pqrs.tipo_d.descripcion,
            'estado': 'Creada',
        }
        enviar_notificacion(
            destinatario=current_user.email,
            asunto='PQRS Creada Exitosamente',
            tipo_accion='pqrs_creada',
            datos=datos
        )

        # Crear carpeta por ID
        ruta_archivos = os.path.join('static', 'pqrs', str(nueva_pqrs.id))
        os.makedirs(ruta_archivos, exist_ok=True)

        # Procesar múltiples archivos
        archivos = request.files.getlist('archivos[]')

        for archivo in archivos:
            if archivo and allowed_file(archivo.filename):
                nombre_original = secure_filename(archivo.filename)
                nombre_encriptado = str(uuid.uuid4()) + os.path.splitext(nombre_original)[1]
                archivo_path = os.path.join(ruta_archivos, nombre_encriptado)
                archivo.save(archivo_path)

                nuevo_archivo = PQRSArchivo(
                    id_pqrs=nueva_pqrs.id,
                    nombre_original=nombre_original,
                    nombre_encriptado=nombre_encriptado
                )
                db.session.add(nuevo_archivo)

        db.session.commit()
        registrar_log(current_user.id,"PQRS", "Crea PQRS id " + str(nueva_pqrs.id))
        flash("Tu PQRS ha sido registrada correctamente.", "success")
        return redirect(url_for('pqrs.listar'))
    datos = DatosConjunto.query.first()
    tipos_pqrs = tipo_pqrs.query.all()
    return render_template('pqrs/crear_pqrs.html', tipos_pqrs=tipos_pqrs, descripciones_pqrs=[], datos=datos)


@pqrs_bp.route('/obtener_descripciones/<int:id_tipo>')
@login_required
@require_permission('Residente')
def obtener_descripciones(id_tipo):
    if id_tipo:
        descripciones = descripcion_pqrs.query.filter_by(id_tipo=id_tipo).all()
        return jsonify([{"id": d.id, "tipo": d.tipo,"descripcion": d.descripcion} for d in descripciones])
    
@pqrs_bp.route('/descargar_archivo/<int:id_archivo>')
@login_required
@require_permission('Residente')
def descargar_archivo(id_archivo):
    archivo = PQRSArchivo.query.get_or_404(id_archivo)

    # Subir un nivel desde app para encontrar static/
    base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    ruta_archivo = os.path.join(base_dir, 'static', 'pqrs', str(archivo.id_pqrs), archivo.nombre_encriptado)

    if not os.path.exists(ruta_archivo):
        flash("El archivo no existe en el servidor.", "danger")
        return redirect(url_for('pqrs.ver_pqrs', id=archivo.id_pqrs))

    registrar_log(current_user.id,"PQRS", "Descarga archivo"+ str(archivo.nombre_original)+" de la PQRS id"+ str(archivo.id_pqrs))
    
    return send_file(
        ruta_archivo,
        as_attachment=True,
        download_name=archivo.nombre_original
    )


@pqrs_bp.route('/editar_pqrs/<int:pqrs_id>', methods=['GET', 'POST'])
@login_required
@require_permission('Residente')
def editar_pqrs(pqrs_id):
    pqrs = PQRS.query.get_or_404(pqrs_id)

    if request.method == 'POST':
        pqrs.id_tipo = request.form.get('id_tipo')
        pqrs.tipo = request.form.get('id_descripcion')
        pqrs.observacion = request.form.get('observacion')
        archivoo = request.files.get('archivo')

        if archivoo:
            if archivoo and allowed_file(archivoo.filename):
                pqrs.archivo = archivoo.read()  # Leer archivo en binario
                pqrs.nombre_archivo = secure_filename(archivoo.filename)
                pqrs.tipo_archivo = archivoo.content_type  # Obtener tipo MIME
            elif archivoo:
                flash('Error: Formato de archivo no permitido.', 'danger')
                return redirect(url_for('pqrs.editar_pqrs'))
        else:
            pqrs.archivo = None
            pqrs.nombre_archivo = None
            pqrs.tipo_archivo = None 


        db.session.commit()

        datos = {
            'usuario': current_user.nombre,
            'radicado': pqrs.numero_radicado,
            'tipop': pqrs.tipo_p.nombre,
            'estado': 'Creada',
        }
        enviar_notificacion(
            destinatario=current_user.email,
            asunto='PQRS Modificada Exitosamente',
            tipo_accion='pqrs_editada',
            datos=datos
        )

        registrar_log(current_user.id,"PQRS", "Edita Pqrs id "+str(pqrs.id))
        flash('La solicitud PQRS ha sido actualizada correctamente.', 'success')
        return redirect(url_for('pqrs.listar'))

    tipos_pqrs = tipo_pqrs.query.all()
    estados = estados_pqrs.query.all()
    
    return render_template('pqrs/editar_pqrs.html', pqrs=pqrs, tipos_pqrs=tipos_pqrs, estados=estados, descripciones_pqrs=[])


@pqrs_bp.route('/eliminar_pqrs/<int:id>', methods=['POST'])
@login_required
@require_permission('Residente')
def eliminar_pqrs(id):
    """Eliminar una reserva."""
    respuesta = PQRS.query.get_or_404(id)

    if respuesta.id_estado != 1:  # Solo se pueden eliminar la pqrs
        flash("No se puede eliminar la pqrs ya esta en tramite.", "danger")
        return redirect(url_for('pqrs.listar'))
    
    datos = {
        'usuario': current_user.nombre,
        'radicado': respuesta.numero_radicado,
        'tipop': respuesta.tipo_p.nombre,
        'estado': 'Eliminada',
        }
    enviar_notificacion(
        destinatario=current_user.email,
        asunto='PQRS Eliminada Exitosamente',
        tipo_accion='pqrs_eliminada',
        datos=datos
        )

    db.session.delete(respuesta)
    db.session.commit()

    

    registrar_log(current_user.id,"PQRS", "Elimina Pqrs id "+str(respuesta.id))
    flash("Pqrs eliminada correctamente.", "success")
    return redirect(url_for('pqrs.listar'))


@pqrs_bp.route('/descargar_pdf/<int:id_pqrs>')
@login_required
def descargar_pdf_pqrs(id_pqrs):
    pqrs = PQRS.query.get_or_404(id_pqrs)
    historial = HistorialPQRS.query.filter_by(id_pqrs=id_pqrs).all()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 50
    y = height - margin

    # Logo
    base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    logo_path = os.path.join(base_dir, 'static', 'img', 'logo.png')
    # Insertar el logo más grande y centrado
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        logo_width = 250
        logo_height = 100
        c.drawImage(logo, (width - logo_width) / 2, y - logo_height, width=logo_width, preserveAspectRatio=True, mask='auto')

    y -= logo_height + 5  # ajusta el espacio debajo del logo
    


    # Encabezado
    c.setFillColor(colors.HexColor("#d6b456"))
    c.rect(margin, y, width - 2 * margin, 30, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y + 8, "COMPROBANTE PQRS")
    y -= 40

    # Subtítulo
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, y, f"Número de Radicado: {pqrs.numero_radicado}")
    y -= 30

    # Sección de datos generales
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(colors.HexColor("#d6b456"))
    c.drawString(margin, y, "Información General")
    y -= 15
    c.setStrokeColor(colors.HexColor("#d6b456"))
    c.line(margin, y, width - margin, y)
    y -= 20
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)

    datos = [
        ("Usuario", f"{pqrs.usuario.nombre} (ID: {pqrs.usuario.identificacion})"),
        ("Unidad Residencial", f"Torre: {pqrs.usuario.casa.torre.nombre} - Apartmento: {pqrs.usuario.casa.apartamento.numero}"),
        ("Fecha de Radicación", pqrs.fecha_creacion.strftime('%Y-%m-%d')),
        ("Tipo", pqrs.tipo_p.nombre),
        ("Requerimiento", pqrs.tipo_d.tipo),
        ("Descripción", pqrs.tipo_d.descripcion),
        ("Observación Adicional", pqrs.observacion),
        ("Fecha límite de Respuesta", pqrs.fecha_max.strftime('%Y-%m-%d')),
        ("Estado Actual", pqrs.estado.nombre),
    ]

    for etiqueta, valor in datos:
        c.setFont("Helvetica-Bold", 11)
        etiqueta_texto = f"{etiqueta}:"
        c.drawString(60, y, etiqueta_texto)

        text_width = c.stringWidth(etiqueta_texto, "Helvetica-Bold", 11)
        c.setFont("Helvetica", 11)

        if isinstance(valor, str) and len(valor) > 90:
            wrapped_lines = wrap(valor, width=90)
            c.drawString(60 + text_width + 10, y, wrapped_lines[0])
            y -= 15
            for line in wrapped_lines[1:]:
                c.drawString(60, y, line)  # alineado a la izquierda para multilinea
                y -= 15
        else:
            c.drawString(60 + text_width + 10, y, str(valor))
            y -= 18

        if y < 100:
            c.showPage()
            y = height - 80
            c.setFont("Helvetica", 11)
            c.setFillColor(colors.black)

    

    # Historial de respuestas
    y -= 10
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(colors.HexColor("#d6b456"))
    c.drawString(margin, y, "Historial de Respuestas")
    y -= 15
    c.setStrokeColor(colors.HexColor("#d6b456"))
    c.line(margin, y, width - margin, y)
    y -= 20
    c.setFillColor(colors.black)

    if historial:
        for item in historial:
            if item.estado_actual == "1":
                estado = "Registrado"
            elif item.estado_actual == "2":
                estado = "En Proceso"
            else:
                estado = "Resuelta"
                

            c.setFont("Helvetica-Bold", 10)
            c.drawString(margin, y, f"Fecha: {item.fecha_respuesta.strftime('%Y-%m-%d')}")
            c.drawString(margin + 200, y, f"Estado: {estado}")
            y -= 15
            if item.respuesta:
                c.setFont("Helvetica", 10)
                c.drawString(margin + 20, y, f"Respuesta: {item.respuesta}")
                y -= 15
            y -= 5
            if y < 100:
                c.showPage()
                y = height - margin
    else:
        c.setFont("Helvetica", 10)
        c.drawString(margin, y, "No hay respuestas registradas.")

    # Guardar y devolver PDF
    c.save()
    buffer.seek(0)

    registrar_log(current_user.id,"PQRS", "Descar Comrprobante PQRS")

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Comprobante_PQRS_{pqrs.numero_radicado}.pdf",
        mimetype='application/pdf'
    )