import os
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, abort, send_from_directory, send_file, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models.facturacion import Factura, ConfiguracionFactura, HistoricoFacturacion, generar_consecutivo_pago
from models.usuario import Usuarios
from models.datos_conjunto import DatosConjunto
from controllers.log import registrar_log
from app import db
from werkzeug.utils import secure_filename
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.graphics.barcode import code128
from controllers.configuracion import require_permission
from reportlab.lib.utils import ImageReader
from sqlalchemy import func, or_, distinct
from controllers.api_mail import enviar_notificacion


factura_bp = Blueprint('facturacion', __name__)

# Ruta para ver las facturas del usuario
@factura_bp.route('/')
@login_required
@require_permission('Residente')
def listar_facturas():
    """ Muestra las facturas del usuario mes a mes """
    
    facturas = Factura.query.filter_by(usuario_id=current_user.id).order_by(Factura.year.desc(), Factura.mes.desc()).first()
    ultimaFactura = HistoricoFacturacion.query.filter(
    HistoricoFacturacion.id_factura == facturas.id,
    HistoricoFacturacion.id_usuario == facturas.usuario_id,
    or_(
        #HistoricoFacturacion.estado == "En espera de comprobación",     
        HistoricoFacturacion.estado == "Pendiente"
    )
    ).order_by(HistoricoFacturacion.id.desc()).first()

    ultimaFacturas = HistoricoFacturacion.query.filter(
    HistoricoFacturacion.id_factura == facturas.id,
    HistoricoFacturacion.id_usuario == facturas.usuario_id,
    or_(
        HistoricoFacturacion.estado == "En espera de comprobación",     
        HistoricoFacturacion.estado == "Pendiente",
        HistoricoFacturacion.estado == "Aprobada"
    )
    ).order_by(HistoricoFacturacion.id.desc()).first()

    monto_total_pagado = db.session.query(func.sum(HistoricoFacturacion.monto_pagado))\
    .filter(
        HistoricoFacturacion.id_factura == facturas.id,
        HistoricoFacturacion.id_usuario == facturas.usuario_id,
        or_(
            HistoricoFacturacion.estado == "En espera de comprobación",
            HistoricoFacturacion.estado == "Aprobado"
        )
    ).scalar() or 0 # retorna 0 si no hay pagos

# Determinar saldo pagado (considerando abonos)

    # Convertir ambos a float (si trabajas con float)
    monto_total_pagado = float(monto_total_pagado or 0) #100000
    abono = float(facturas.abono or 0) #0
    total_factura = float(facturas.total or 0)
    valor_validacion= float(facturas.validacion or 0) #100000



    # Calcular el saldo pendiente
    saldo_pendiente = valor_validacion - monto_total_pagado
    saldo_pendiente = max(saldo_pendiente, 0) 

    print("Saldo pendiente:", saldo_pendiente)
    # Asegurar que nunca sea negativo
    saldo_pendiente = max(saldo_pendiente, 0)

    registrar_log(current_user.id,"Facturacion", "Lista facturacion")
    return render_template('facturacion/listar_facturas.html', factura=facturas, ultimaFacturas=ultimaFacturas, ultimaFactura=ultimaFactura, valor_Factura=valor_validacion, saldo_pendiente=saldo_pendiente, monto_total_pagado=monto_total_pagado)

@factura_bp.route('/historico_factura/<int:id>/<int:d>', methods=['GET'])
@login_required
@require_permission('Residente')
def listar_historico(id,d):
    facturas = Factura.query.filter_by(id=id).first()
    historial = HistoricoFacturacion.query.filter_by(id_factura=id).order_by(HistoricoFacturacion.fecha_pago.asc()).all()

    registrar_log(current_user.id,"Facturacion", "Lista facturacion")
    return render_template('facturacion/historico_factura_individual.html', historial=historial, factura=facturas, d=d)

@factura_bp.route('/historico_facturas')
@login_required
def historico_facturas():
    

    year = request.args.get('year')
    mes = request.args.get('mes')
    estado = request.args.get('estado')

    query = Factura.query.filter_by(usuario_id=current_user.id)

    if year:
        query = query.filter(Factura.year == int(year))
    if mes:
        query = query.filter(Factura.mes == int(mes))
    if estado:
        query = query.filter(Factura.estado == estado)

    facturas = query.order_by(Factura.year.desc(), Factura.mes.desc()).all()

    anios = db.session.query(distinct(Factura.year)).order_by(Factura.year).all()
    anios = [a[0] for a in anios]  # Convertir a lista simple

    #facturas = Factura.query.filter(
     #   Factura.usuario_id == current_user.id
    #).order_by(Factura.year.desc(), Factura.mes.desc()).all()


    registrar_log(current_user.id,"Facturacion", "Historico facturacion")
    return render_template('facturacion/historico_facturas.html', facturas=facturas, anios=anios)

# Ruta para subir el comprobante de pago
@factura_bp.route('/factura/subir_comprobante/<int:factura_id>', methods=['POST'])
@login_required
@require_permission('Residente')
def subir_comprobante(factura_id):
    """Permite al usuario subir el comprobante de pago y cambia el estado a 'En espera de comprobación'."""
    
    factura = HistoricoFacturacion.query.get_or_404(factura_id)

    if 'comprobante' not in request.files:
        flash("No se seleccionó ningún archivo.", "danger")
        return redirect(url_for('factura.ver_facturas'))

    file = request.files['comprobante']
    
    if file.filename == '':
        flash("Debe seleccionar un archivo válido.", "danger")
        return redirect(url_for('factura.ver_facturas'))
    
    if file:
        # Crear carpeta del usuario en `static/facturacion/`
        base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        usuario_path = os.path.join(base_dir, 'static', 'facturacion', 'comprobantes', f'usuario_{current_user.id}')
        os.makedirs(usuario_path, exist_ok=True)

        # Guardar el archivo con su nombre original
        filename = secure_filename(file.filename)
        file_path = os.path.join(usuario_path, filename)
        file.save(file_path)

        # Guardar en base de datos
        factura.comprobante_original = file
        factura.comprobante_encriptado = filename
        factura.comprobante_path= file_path
        factura.estado = "En espera de comprobación",
        factura.fecha_subio_pago=datetime.today()
        db.session.commit()

        datos = {
            'usuario': factura.usuario.nombre,
            'factura': factura.consecutivo_pago,
            'valor': factura.monto_pagado,  
            'estado': factura.estado
        }
        enviar_notificacion(
            destinatario=factura.usuario.email,
            asunto='Factura Subida',
            tipo_accion='factura_subida',
            datos=datos
        )

        flash("Comprobante subido con éxito. Su pago está en espera de verificación.", "success")
        registrar_log(current_user.id, "Facturacion","Sube comprobante de pago factura "+str(factura.id))
        return redirect(url_for('facturacion.listar_historico', id=factura_id, d=0))
    return redirect(url_for('facturacion.listar_historico', id=factura_id, d=0))

#este es el que sirve
@factura_bp.route('/ver_comprobante/<int:id>')
@login_required
@require_permission('Residente')
def ver_comprobante1(id):
    factura = HistoricoFacturacion.query.get_or_404(id)
    archivo = factura.comprobante_encriptado

    if not archivo:
        abort(404, description="Comprobante no encontrado.")

    registrar_log(current_user.id,"Facturacion", "Descarga comprobante subido factura id "+str(factura.id))

    # Obtener la carpeta de almacenamiento
    base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    carpeta_comprobantes = os.path.join(base_dir, 'static', 'facturacion', 'comprobantes', f'usuario_{current_user.id}')

    return send_from_directory(carpeta_comprobantes, archivo)


@factura_bp.route('/descargar_factura/<int:id>', methods=['GET','POST'])
@login_required
@require_permission('Residente')
def descargar_factura(id):
    """Genera y descarga la factura en PDF con los datos de facturación."""
    
    factura = Factura.query.get_or_404(id)

    if request.method == 'POST':
        abono = request.form.get('abono')
        if abono:
            try:
                abono = float(abono)

                if 0 <= abono <= factura.total:
                    valor=abono
                    tipo="Abono"
                    #factura.total -= abono
                    #flash(f"Abono de ${abono:,.2f} aplicado correctamente.", "success")
                else:
                    flash("El abono ingresado no es válido.", "danger")
                    return redirect(url_for('facturacion.listar_facturas'))
            except ValueError:
                flash("Error: abono inválido.", "danger")
                return redirect(url_for('facturacion.listar_facturas'))
        else:
            valor=factura.total
            tipo="Pago Total"

        
   
    # Validar si ya existe un pago igual
    pago_existente = HistoricoFacturacion.query.filter_by(
            id_factura=factura.id,
            id_usuario=factura.usuario_id,
           # monto_pagado=valor,
            #tipo_pago=tipo,
            estado="Pendiente"
        ).first()
    
    monto_total_pagado = db.session.query(func.sum(HistoricoFacturacion.monto_pagado))\
    .filter(
        HistoricoFacturacion.id_factura == factura.id,
        HistoricoFacturacion.id_usuario == factura.usuario_id,
        or_(
            HistoricoFacturacion.estado == "Pendiente",
            HistoricoFacturacion.estado == "En espera de comprobación"
        )
    ).scalar() or 0 # retorna 0 si no hay pagos

    
    if pago_existente:
            if tipo == "Pago Total":
                pago_existente.tipo_pago=tipo
                pago_existente.monto_pagado=float(valor)-float(monto_total_pagado or 0)
            elif valor != pago_existente.monto_pagado:
                pago_existente.monto_pagado = valor
                pago_existente.tipo_pago=tipo
            pago=pago_existente
            db.session.commit()
    elif monto_total_pagado > 0:
        pago = HistoricoFacturacion(
            id_factura=factura.id,
            id_usuario=factura.usuario_id,
            monto_pagado=float(valor)-float(monto_total_pagado or 0),
            tipo_pago=tipo,
            comprobante_original= None,
            consecutivo_pago =generar_consecutivo_pago(),
            estado="Pendiente",
            comprobacion=1
        )
        db.session.add(pago)
        db.session.commit()
           
    else:
        pago = HistoricoFacturacion(
            id_factura=factura.id,
            id_usuario=factura.usuario_id,
            monto_pagado=float(valor)-float(monto_total_pagado or 0),
            tipo_pago=tipo,
            comprobante_original= None,
            consecutivo_pago =generar_consecutivo_pago(),
            estado="Pendiente"
        )
        db.session.add(pago)
        db.session.commit()


    # Generar la factura en PDF
    filepath = generar_factura_pdf(pago)

    registrar_log(current_user.id,"Facturacion","Descargó factura consecutivo "+str(pago.consecutivo_pago) +" del mes "+str(factura.mes)+" - año " +str(factura.year))

    if os.path.exists(filepath):
        flash(f"Se genero la factura.", "success")
        return send_file(filepath, as_attachment=True)
        
    else:
        flash("Error al generar la factura.", "danger")
        return redirect(url_for('facturacion.listar_facturas'))


def generar_factura_pdf(pago):
    """Genera el PDF de la factura de administración y lo guarda en el sistema."""
    
    # Obtener datos de la empresa
    datos_empresa = DatosConjunto.query.first()
    if not datos_empresa:
        raise ValueError("No hay datos del conjunto registrados en la base de datos.")

    # Definir la carpeta de facturación
    factura_dir = os.path.abspath(os.path.join("static", "Reservas", "facturas", "usuarios", str(pago.usuario.id)))
    os.makedirs(factura_dir, exist_ok=True)

    # Nombre seguro del archivo
    filename = secure_filename(f"Factura_{pago.consecutivo_pago}.pdf")
    filepath = os.path.join(factura_dir, filename)

    # Configurar el PDF
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    margin = 50
    y = height - margin

    # **Logo**
    base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    logo_path = os.path.join(base_dir, 'static', 'img', 'logo.png')
    if os.path.exists(logo_path):
        logo = ImageReader(logo_path)
        logo_width = 250
        logo_height = 100
        c.drawImage(logo, (width - logo_width) / 2, y - logo_height, width=logo_width, preserveAspectRatio=True, mask='auto')
        y -= logo_height + 5  # Ajusta el espacio debajo del logo

    # **Encabezado**
    c.setFillColor(colors.HexColor("#d6b456"))
    c.rect(margin, y, width - 2 * margin, 30, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    titulo=("RECIBO DE ADMINISTRACIÓN - "+pago.consecutivo_pago )
    c.drawCentredString(width / 2, y + 8, titulo)
    y -= 30

    # **Subtítulo**
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.black)
    #c.drawCentredString(width / 2, y, "RECIBO DE ADMINISTRACIÓN")
    #y -= 33

    # Meses en formato textual
    meses = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    # **Información del usuario**
    user_data = [
        ["NOMBRE:", pago.usuario.nombre],
        ["UNIDAD RESIDENCIAL:", "Torre: "+str(pago.usuario.casa.torre.nombre)+ " Apartamento: "+ str(pago.usuario.casa.apartamento.numero)],
        ["MES - AÑO:", f"{meses[pago.factura.mes]} - {pago.factura.year}"],
        ["FECHA DE EMISIÓN:", str(pago.factura.fecha_emision)],
        ["FECHA DE VENCIMIENTO:", str(pago.factura.fecha_max_pago)]
    ]
    
    # Tabla con información del usuario
    user_table = Table(user_data, colWidths=[150, 250])
    user_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey)
    ]))
    user_table.wrapOn(c, width, height)
    y -= 100
    user_table.drawOn(c, 50, y)

    # **Tabla de valores**
    if pago.tipo_pago == "Abono":
        data = [
            ["DESCRIPCIÓN", "VALOR"],
            ["Abono Tarifa Administración", f"$ {pago.monto_pagado:,.0f}"],
            ["TOTAL A PAGAR", f"$ {pago.monto_pagado:,.0f}"]
        ]
        monto_str = int(pago.monto_pagado)
    else:
        interes = (pago.factura.mora or 0)
        saldo_anterior = (pago.factura.saldo_anterior or 0)
        abono = (pago.factura.abono or 0)
        descuento = (pago.factura.descuento or 0)
        monto_str = int((pago.factura.valor_base + interes + saldo_anterior) - int(descuento) - int(abono))

        if pago.comprobacion == 1:
            
            abono+=float(pago.monto_pagado)
            valor=pago.factura.valor_base
            monto_str = int(pago.monto_pagado)
            data = [
                ["DESCRIPCIÓN", "VALOR"],
                ["Tarifa Administración", f"$ {valor:,.0f}"],
                ["Saldo Anterior", f"$ {saldo_anterior:,.0f}"],
                ["Descuento Aplicado", f"$ {descuento:,.0f}"],
                ["Intereses Mora", f"$ {interes:,.0f}"],
                ["Abono", f"$ {abono:,.0f}"],
                ["TOTAL A PAGAR", f"$ {monto_str:,.0f}"]
            ]

        elif pago.factura.saldo_anterior:
            data = [
                ["DESCRIPCIÓN", "VALOR"],
                ["Tarifa Administración", f"$ {pago.factura.valor_base:,.0f}"],
                ["Saldo Anterior", f"$ {saldo_anterior:,.0f}"],
                ["Descuento Aplicado", f"$ {descuento:,.0f}"],
                ["Intereses Mora", f"$ {interes:,.0f}"],
                ["TOTAL A PAGAR", f"$ {monto_str:,.0f}"]
            ]

        elif pago.factura.abono:
            data = [
                ["DESCRIPCIÓN", "VALOR"],
                ["Tarifa Administración", f"$ {pago.factura.valor_base:,.0f}"],
                ["Saldo Anterior", f"$ {saldo_anterior:,.0f}"],
                ["Descuento Aplicado", f"$ {descuento:,.0f}"],
                ["Intereses Mora", f"$ {interes:,.0f}"],
                ["Abono", f"$ {abono:,.0f}"],
                ["TOTAL A PAGAR", f"$ {monto_str:,.0f}"]
            ]
            
        else:
            data = [
                ["DESCRIPCIÓN", "VALOR"],
                ["Tarifa Administración", f"$ {pago.monto_pagado:,.0f}"],
                ["TOTAL A PAGAR", f"$ {pago.monto_pagado:,.0f}"]
            ]
            monto_str = int(pago.monto_pagado)
    # Tabla con los valores de la factura
    table = Table(data, colWidths=[300, 150])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))
    table.wrapOn(c, width, height)
    y -= table._height + 30
    table.drawOn(c, 50, y)

    # **Código de barras**
    codigo_empresa = datos_empresa.codigo_cuenta
    numero_cuenta = datos_empresa.numero_cuenta
    numero_apartamento = f"{pago.usuario.casa.torre.nombre}{pago.usuario.casa.apartamento.numero}"
    fecha_vencimiento = pago.factura.fecha_max_pago.strftime("%Y%m%d")
    datos_sin_parentesis = f"415{codigo_empresa}8020{numero_apartamento}{numero_cuenta}3900{monto_str}96{fecha_vencimiento}"
    datos = f"(415){codigo_empresa}(8020){numero_apartamento}{numero_cuenta}(3900){monto_str}96{fecha_vencimiento}"

    # Generar y dibujar el código de barras
    barcode = code128.Code128(datos_sin_parentesis, barHeight=60, barWidth=1.2)
    y -= 100
    barcode.drawOn(c, (width - 400) / 2, y)  # Centrado del código de barras
    c.setFont("Helvetica-Bold", 10)
    c.drawString(width - 450, y - 15, datos)  # Centrado del texto del código de barras

    # Instrucciones de pago
    instrucciones = [
        "INSTRUCCIONES DE PAGO:",
        f"1. Realice el pago a la cuenta {datos_empresa.codigo_cuenta} N° {datos_empresa.numero_cuenta}",
        f"   del Banco de Bogota.",
        f"2. Utilice el código de barras generado para agilizar el proceso si su entidad lo permite.",
        f"3. El pago debe realizarse antes del {pago.factura.fecha_max_pago.strftime('%d/%m/%Y')}.",
        "4. Guarde este comprobante como soporte de su pago."
    ]

    texto_y = y - 40
    c.setFont("Helvetica", 9)
    for linea in instrucciones:
        c.drawString(margin, texto_y, linea)
        texto_y -= 12  # Espacio entre líneas

    # **Guardar el PDF**
    c.showPage()
    c.save()

    return filepath