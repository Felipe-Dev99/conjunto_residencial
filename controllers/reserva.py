from flask import Blueprint, Response, render_template, request, redirect, url_for, flash, send_file, current_app, send_from_directory, send_file, abort
from flask_login import login_required, current_user
from app import db, login_manager
from models.reserva import Reserva, Espacios_reserva, generar_numero_radicado_reserva
from models.reserva import Facturas
from models.usuario import Usuarios
from datetime import datetime, time, timedelta
import uuid
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
import io
from sqlalchemy.orm import load_only
from controllers.configuracion import require_permission
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from models.datos_conjunto import DatosConjunto
from sqlalchemy.exc import SQLAlchemyError
from controllers.log import registrar_log
from textwrap import wrap
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from controllers.api_mail import enviar_notificacion


reserva_bp = Blueprint("reserva", __name__)

@reserva_bp.route('/')
@login_required
@require_permission('Residente')
def mis_agendas():
    """Mostrar las reservas del usuario."""
    # Registrar en el log
    registrar_log(current_user.id,"Reserva", "Visualiza reserva")

    #agendas = Reserva.query.filter_by(id_usuario=current_user.id).all()

    page = request.args.get('page', 1, type=int)
    per_page = 5
    agendas = Reserva.query.filter_by(id_usuario=current_user.id).order_by(Reserva.fecha.desc()).paginate(page=page, per_page=per_page)
   
    return render_template('reservas/mis_agendas.html', agendas=agendas)

@reserva_bp.route('/agendar_salon', methods=['GET', 'POST'])
@login_required
@require_permission('Residente')
def agendar_salon():
    if request.method == 'POST':
        espacio = request.form['id_espacio']
        fecha = request.form['fecha']
        horario = request.form['horario']
        descripcion = request.form['descripcion']


        # Convertir valores a datetime
        fecha_dt = datetime.strptime(fecha, "%Y-%m-%d").date()
        hoy = datetime.today().date()
        fecha_minima = hoy + timedelta(days=2)  # Se requiere al menos 2 días de anticipación

        # Validar que la fecha sea mayor a la fecha en la que se agenda
        if fecha_dt < hoy:
            flash("No es posible reservar el salón en la fecha seleccionada, estas seleccionando una fecha pasada.", "danger")
            return render_template('reservas/agendar_salon.html')     
        

        # Validar que la fecha tenga mínimo dos días de anticipación
        if fecha_dt < fecha_minima:
            flash("No es posible reservar el salón en la fecha seleccionada, ya que se debe reservar con al menos dos días de anticipación.", "danger")
            return render_template('reservas/agendar_salon.html')

        # Validar que los campos no estén vacíos
        if not fecha or not horario or not descripcion:
            flash('Error: Todos los campos son obligatorios.', 'danger')
            return render_template('reservas/agendar_salon.html')

        # Validar que la descripción no supere los 300 caracteres
        if len(descripcion) > 300:
            flash('Error: La descripción no puede superar los 300 caracteres.', 'danger')
            return render_template('reservas/agendar_salon.html')

        # Validar que la fecha y el horario no estén ocupados (evitar duplicados)
        reserva_existente = Reserva.query.filter_by(id_espacio_reserva=espacio, fecha=fecha, horario=horario).first()
        if reserva_existente:
            flash('Error: El espacio ya esta agendado en la fecha y el horario seleccionado. Por favor elige otra fecha u horario.', 'danger')
            return render_template('reservas/agendar_salon.html')

        numero_radicadoo = generar_numero_radicado_reserva()

       # Crear la nueva reserva
        nueva_reserva = Reserva(
            id_usuario=current_user.id,
            id_espacio_reserva=espacio,
            numero_radicado=numero_radicadoo,
            fecha=fecha_dt,
            horario=horario,
            descripcion=descripcion,
            id_estado=1
        )
        db.session.add(nueva_reserva)
        db.session.commit()

        espacio_valor = Espacios_reserva.query.filter_by(id=espacio).first()
        nueva_factura = Facturas(
            id_solicitud=nueva_reserva.id,
            id_usuario=current_user.id,
            monto=espacio_valor.valor,
            fecha_emision=datetime.now()
        )
        db.session.add(nueva_factura)

        actualizar_factura = Reserva.query.filter_by(id=nueva_reserva.id).first()
        actualizar_factura.id_factura = nueva_factura.id
        db.session.commit()

        datos = {
            'usuario': current_user.nombre,
            'radicado': nueva_reserva.numero_radicado,
            'fecha': nueva_reserva.fecha.strftime('%Y-%m-%d'),
            'hora': nueva_reserva.horario,
            'espacio': nueva_reserva.espacios.nombre,
            'estado': 'Registrada'
        }
        enviar_notificacion(
            destinatario=current_user.email,
            asunto='Reserva registrada exitosamente',
            tipo_accion='reserva_creada',
            datos=datos
        )

        registrar_log(current_user.id,"Reserva", "Crea reserva id "+str(nueva_reserva.id)+" fecha "+str(fecha)+" espacio "+str(espacio))

        flash("Solicitud enviada. Estado: Pendiente. Factura generada.", "success")
        
        return redirect(url_for('reserva.mis_agendas'))
    
    espacios = Espacios_reserva.query.all()
    return render_template('reservas/agendar_salon.html', espacios=espacios)


@reserva_bp.route('/descargar_factura/<int:id>', methods=['GET'])
@login_required
@require_permission('Residente')
def descargar_factura(id):
    
    #factura = Facturas.query.filter_by(id_solicitud = id).first() # se supone que me trae el dato segun el filtro

    Forma_anterior = Facturas.query.get_or_404(id)
    
    # Generar la factura en PDF
    filepath = generar_factura_pdf(Forma_anterior)

    registrar_log(current_user.id,"Reserva", "Genera Factura Reserva id "+str(id))
    
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        flash("Error al generar la factura.", "danger")
        return redirect(url_for('reserva.mis_agendas'))


def generar_factura_pdf(factura):
    datos_empresa = DatosConjunto.query.first()

    factura_dir = os.path.abspath(os.path.join("static", "facturas", "reservas", str(factura.usuario.id)))
    os.makedirs(factura_dir, exist_ok=True)

    filename = f"Factura_Reserva_{factura.id}.pdf"
    filepath = os.path.join(factura_dir, filename)

    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    y = height - 30  # Punto de partida desde arriba

    # Logo centrado
    logo_path = os.path.join("static", "img", "logo.png")
    if os.path.exists(logo_path):
        logo_width = 250
        logo_height = 100
        x_logo = (width - logo_width) / 2
        c.drawImage(logo_path, x_logo, y - logo_height, width=logo_width, height=logo_height, preserveAspectRatio=True)
        y -= logo_height + 20  # Espacio después del logo

    # Nombre del conjunto
    titulo = f"Numero Reserva {factura.solicitud.numero_radicado}"
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, y, titulo)
    y -= 30

    # Título
    #titulo = f"Factura Reserva {factura.solicitud.espacios.nombre} - {factura.solicitud.espacios.descripcion}"
    #c.setFont("Helvetica-Bold", 14)
    #c.drawCentredString(width / 2, y, titulo)
    #y -= 40

    # Tabla de información del usuario
    user_data = [
        ["NOMBRE:", factura.usuario.nombre],
        ["UNIDAD RESIDENCIAL:", "Torre: "+str(factura.usuario.casa.torre.nombre)+" Apartamento: "+str(factura.usuario.casa.apartamento.numero)],
        ["ESPACIO:", str(factura.solicitud.espacios.nombre)],
        ["FECHA:", str(factura.solicitud.fecha)]
    ]

    user_table = Table(user_data, colWidths=[120, 200])
    user_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey)
    ]))

    user_table_width, user_table_height = user_table.wrap(0, 0)
    user_table.drawOn(c, 50, y - user_table_height)
    y -= user_table_height + 30

    # Tabla de obligaciones
    data = [
        ["OBLIGACIONES", "VALOR"],
        ["Pago base reserva", f"$ {factura.monto:,.0f}"],
        ["TOTAL", f"$ {factura.monto:,.0f}"]
    ]

    table = Table(data, colWidths=[300, 150])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))

    table_width, table_height = table.wrap(0, 0)
    table.drawOn(c, 50, y - table_height)
    y -= table_height + 30

    # Código de barras
    codigo_empresa = datos_empresa.codigo_cuenta
    numero_cuenta = datos_empresa.numero_cuenta
    monto_pesos = factura.monto
    numero_apartamento = str(factura.usuario.casa.torre.nombre + factura.usuario.casa.apartamento.numero)
    monto_str = int(monto_pesos)
    fecha_vencimiento = datetime(2025, 3, 31).strftime("%Y%m%d")

    datos_sin_parentesis = f"415{codigo_empresa}8020{numero_apartamento}{numero_cuenta}3900{monto_str}96{fecha_vencimiento}"
    datos = f"(415){codigo_empresa}(8020){numero_apartamento}{numero_cuenta}(3900){monto_str}(96){fecha_vencimiento}"

    barcode = code128.Code128(datos_sin_parentesis, barHeight=60, barWidth=1.2)
    barcode.drawOn(c, 60, y - 60)
    y -= 75

    c.setFont("Helvetica-Bold", 10)
    c.drawString(120, y, datos)

    c.showPage()
    c.save()

    return filepath

@reserva_bp.route('/editar_reserva/<int:id>', methods=['GET', 'POST'])
@login_required
@require_permission('Residente')
def editar_reserva(id):
    """Modificar la fecha y hora de una reserva."""
    agenda = Reserva.query.get_or_404(id)

    fecha_anterior = agenda.fecha.strftime('%Y-%m-%d')
    horario_anterior = agenda.horario

    if request.method == 'POST':
        espacio = request.form['id_espacio']
        nueva_fecha = request.form['fecha']
        nuevo_horario = request.form['horario']
        nueva_descripcion = request.form['descripcion']

        # Convertir valores a datetime
        fecha_dt = datetime.strptime(nueva_fecha, "%Y-%m-%d").date()
        hoy = datetime.today().date()
        fecha_minima = hoy + timedelta(days=2)  # Se requiere al menos 2 días de anticipación
        
        # Validar que la fecha sea mayor a la fecha en la que se agenda
        if fecha_dt < hoy:
            flash("No es posible reservar el salón en la fecha seleccionada, estas seleccionando una fecha pasada.", "danger")
            return redirect(url_for('reserva.editar_reserva', id=agenda.id))
        
        # Validar que la fecha tenga mínimo dos días de anticipación
        if fecha_dt < fecha_minima:
            flash("No es posible reservar el salón en la fecha seleccionada, ya que se debe reservar con al menos dos días de anticipación.", "danger")
            return redirect(url_for('reserva.editar_reserva', id=agenda.id))

        # Verificar si ya existe una reserva en la misma fecha y horario (excepto la actual)
        reserva_existente = Reserva.query.filter(
            Reserva.id_espacio_reserva == espacio,
            Reserva.fecha == nueva_fecha,
            Reserva.horario == nuevo_horario,
            Reserva.id != agenda.id  # Excluir la reserva actual
        ).first()

        if reserva_existente:
            flash('Error: La fecha y el horario ya están reservados. Por favor elige otra fecha u horario.', 'danger')
            return render_template('reservas/editar_agenda.html', agenda=agenda)

        # Actualizar los valores de la reserva
        agenda.id_espacio_reserva=espacio
        agenda.fecha = nueva_fecha
        agenda.horario = nuevo_horario
        agenda.descripcion = nueva_descripcion
        db.session.commit()

        datos = {
            'usuario': current_user.nombre,
            'radicado': agenda.numero_radicado,
            'fecha_anterior': fecha_anterior,
            'horario_anterior': horario_anterior,
            'fecha': agenda.fecha.strftime('%Y-%m-%d'),
            'hora': agenda.horario,
            'espacio': agenda.espacios.nombre,
            'estado': 'Registrada'
        }
        enviar_notificacion(
            destinatario=current_user.email,
            asunto='Reserva modificada exitosamente',
            tipo_accion='reserva_editada',
            datos=datos
        )


        registrar_log(current_user.id,"Reserva", "Edita Reserva")

        flash("Reserva actualizada correctamente.", "success")
        return redirect(url_for('reserva.mis_agendas'))
    espacios = Espacios_reserva.query.all()
    return render_template('reservas/editar_reserva.html', agenda=agenda, espacios=espacios)


@reserva_bp.route('/eliminar_agenda/<int:id>', methods=['POST'])
@login_required
@require_permission('Residente')
def eliminar_agenda(id):
    """Eliminar una reserva."""
    agenda = Reserva.query.get_or_404(id)

    if agenda.id_estado != 1:  # Solo se pueden eliminar reservas pendientes
        flash("No se puede eliminar una reserva ya aprobada.", "danger")
        return redirect(url_for('reserva.mis_agendas'))

    db.session.delete(agenda)
    db.session.commit()

    datos = {
        'usuario': current_user.nombre,
        'radicado': agenda.numero_radicado,
        'fecha': agenda.fecha.strftime('%Y-%m-%d'),
        'hora': agenda.horario,
        'espacio': agenda.espacios.nombre,
        'estado': 'Cancelada'
        }
    enviar_notificacion(
        destinatario=current_user.email,
        asunto='Reserva Cancelada exitosamente',
        tipo_accion='reserva_eliminada',
        datos=datos
        )

    registrar_log(current_user.id,"Reserva", "Elimina Reserva id "+str(agenda.id))
    flash("Reserva eliminada correctamente.", "success")
    return redirect(url_for('reserva.mis_agendas'))

import os
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@reserva_bp.route('/subir_comprobante/<int:id>', methods=['POST'])
@login_required
@require_permission('Residente')
def subir_comprobante(id):
    reserva = Reserva.query.filter_by(id=id).first()
    agenda = db.session.query(Reserva).filter_by(id=id).first()

    if not agenda:
        flash('Reserva no encontrada.', 'danger')
        return redirect(url_for('reserva.mis_agendas'))

    if 'comprobante' not in request.files:
        flash("No se seleccionó ningún archivo.", "danger")
        return redirect(url_for('reserva.mis_agendas'))

    file = request.files['comprobante']
    
    if file.filename == '':
        flash("Nombre de archivo inválido.", "danger")
        return redirect(url_for('reserva.mis_agendas'))
    
     # Carpeta donde se guardan los comprobantes de las reservas
    upload_folder = current_app.config['UPLOAD_FOLDER']

    # Obtener nombre seguro y generar nombre único
    nombre_original = secure_filename(file.filename)
    extension = os.path.splitext(nombre_original)[1]
    nombre_unico = f"{uuid.uuid4().hex}{extension}"


    # Guardar archivo en la carpeta
    ruta_archivo = os.path.join(upload_folder, nombre_unico)
    file.save(ruta_archivo)

    agenda.comprobante_pago = nombre_original  # Guardar el nombre original
    agenda.comprobante_path = nombre_unico  # Guardar ruta relativa
    agenda.comprobante_pago1 = file.read()
    agenda.comprobante_mimetype = file.mimetype
    agenda.id_estado = 3
    db.session.commit()

    datos = {
        'usuario': current_user.nombre,
        'radicado': agenda.numero_radicado,
        'fecha': agenda.fecha.strftime('%Y-%m-%d'),
        'hora': agenda.horario,
        'espacio': agenda.espacios.nombre,
        'estado': 'Espera de Aprobación'
        }
    enviar_notificacion(
        destinatario=current_user.email,
        asunto='Reserva En Espera de Aprobacion',
        tipo_accion='reserva_en_espera',
        datos=datos
        )

    registrar_log(current_user.id,"Reserva","Sube comprobante de pago Reserva id "+str(agenda.id))
    flash("Comprobante subido correctamente.", "success")
    return redirect(url_for('reserva.mis_agendas'))

@reserva_bp.route('/comprobante/<int:id>')
@require_permission('Residente')
def ver_comprobante(id):
    agenda = Reserva.query.get_or_404(id)
    #agenda = db.session.query(Reserva).filter_by(id=).first()
    #print(type(agenda.comprobante_pago1), len(agenda.comprobante_pago1) if agenda.comprobante_pago1 else "Sin datos")

    if not agenda or not agenda.comprobante_pago1:
        flash('No hay comprobante disponible.', 'warning')
        return redirect(url_for('reserva.mis_agendas'))

    return send_file(io.BytesIO(agenda.comprobante_pago1),
                     mimetype=agenda.comprobante_mimetype,
                     as_attachment=True,
                     download_name="comprobante_pago.pdf")
    #comprobantes_dir = current_app.config['UPLOAD_FOLDER']
    #return send_from_directory(comprobantes_dir, filename)

@reserva_bp.route('/ver_comprobante1/<int:id>')
@require_permission('Residente')
def ver_comprobantee(id):
    agenda = db.session.query(Reserva).filter_by(id=id).first()

    if not agenda or not agenda.comprobante_pago1:
        flash('No hay comprobante disponible.', 'danger')
        return redirect(url_for('reserva.mis_agendas'))

    return Response(agenda.comprobante_pago1, mimetype=agenda.comprobante_mimetype)

#este es el que sirve
@reserva_bp.route('/ver_comprobante/<int:id>')
@login_required
@require_permission('Residente')
def ver_comprobante1(id):
    reserva = Reserva.query.get_or_404(id)
    archivo = reserva.comprobante_path

    if not archivo:
        abort(404, description="Comprobante no encontrado.")

    registrar_log(current_user.id,"Reserva", "Descarga comprobante subido Reserva id "+str(reserva.id))

    # Obtener la carpeta de almacenamiento y el nombre del archivo
    carpeta_comprobantes = current_app.config['UPLOAD_FOLDER']
    #return send_file(carpeta_comprobantes, archivo, as_attachment=True)
    return send_from_directory(carpeta_comprobantes, archivo)

@reserva_bp.route('/descargar_pdf/<int:id>')
@login_required
@require_permission('Residente')
def descargar_pdf_pqrs(id):
    reserva = Reserva.query.get_or_404(id)
    factura = Facturas.query.filter_by(id_solicitud=id).first()

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
    c.drawCentredString(width / 2, y + 8, "COMPROBANTE RESERVA")
    y -= 40

    # Subtítulo
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, y, f"Número de Radicado: {reserva.numero_radicado}")
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
        ("Usuario", f"{reserva.usuario.nombre}"),
        ("Unidad Residencial", f"Torre: {reserva.usuario.casa.torre.nombre} - Apartamento: {reserva.usuario.casa.apartamento.numero}"),
        ("Fecha de Reserva", reserva.fecha.strftime('%Y-%m-%d')),
        ("Espacio", reserva.espacios.nombre),
        ("Horario", reserva.horario),
        ("Descripción", reserva.descripcion),
        ("Valor Reserva", factura.monto),
        ("Estado de la Reserva", reserva.estado.nombre),
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

    
    # Guardar y devolver PDF
    c.save()
    buffer.seek(0)

    registrar_log(current_user.id,"Reserva", "Genera Comprobante de Reserva")

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Comprobante_Rserva_{reserva.numero_radicado}.pdf",
        mimetype='application/pdf'
    )
