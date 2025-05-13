from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, abort, send_from_directory, current_app
from flask_login import login_required, current_user
from datetime import datetime
from werkzeug.utils import secure_filename
from app import db
from models.facturacion import ConfiguracionFactura, Factura, HistoricoFacturacion
from models.usuario import Usuarios
from datetime import date
from controllers.configuracion import require_permission
from controllers.log import registrar_log
import os
from models.casas import Casas, Apartamento, Torre
from models.datos_conjunto import DatosConjunto
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func
from controllers.configuracion import require_permission
from controllers.log import registrar_log
from controllers.api_mail import enviar_notificacion

admin_factura_bp = Blueprint('admin_facturacion', __name__)


@admin_factura_bp.route('/configuracion_facturacion', methods=['GET', 'POST'])
@login_required
@require_permission('Configurar Factura')
def configurar_factura():
    # Obtener la configuración actual o crear una nueva si no existe
    configuracion = ConfiguracionFactura.query.first()
    if not configuracion:
        configuracion = ConfiguracionFactura()
        db.session.add(configuracion)
        db.session.commit()

    if request.method == 'POST':
        try:
            configuracion.tarifa = request.form.get('tarifa', type=float)
            configuracion.dia_habil_pago = request.form.get('dia_habil_pago', type=int)
            configuracion.tasa_descuento = request.form.get('tasa_descuento', type=float)
            configuracion.tasa_mora = request.form.get('tasa_mora', type=float)

            db.session.commit()
            registrar_log(current_user.id,"Admin Facturacion", "Actualiza datos de facturacion")
            flash('Configuración de factura actualizada correctamente.', 'success')
            return redirect(url_for('config.configuracion'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la configuración: {str(e)}', 'danger')

    return render_template('facturacion/configuracion.html', configuracion=configuracion)

@admin_factura_bp.route('/facturas', methods=['GET', 'POST'])
@login_required
@require_permission('Ver Facturacion')
def admin_facturas():
 # Obtener todas las torres y apartamentos
    torres = Torre.query.all()
    apartamentos = Apartamento.query.all()

    # Filtros opcionales
    usuario = request.args.get('usuario', '').strip()
    unidad = request.args.get('unidad', '').strip()

    # Subconsulta para obtener la última factura de cada usuario
    subquery = db.session.query(
        Factura.usuario_id,
        func.max(Factura.id).label('max_id')
    ).group_by(Factura.usuario_id).subquery()

    # Consulta principal
    facturas = Factura.query.join(
        subquery, Factura.id == subquery.c.max_id
    ).join(Usuarios).order_by(Factura.year.desc(), Factura.mes.desc())

    # Aplicar filtro por nombre de usuario
    if usuario:
        facturas = facturas.filter(Usuarios.nombre.ilike(f"%{usuario}%"))

    # Aplicar filtro por unidad residencial
    if unidad:
        try:
            torre, apto = unidad.split('-')  # Divide el valor en torre y apartamento
            torre = torre.strip()  # Limpia espacios en blanco
            apto = apto.strip()  # Limpia espacios en blanco
            facturas = facturas.join(Casas, Usuarios.id_casa == Casas.id).join(Torre, Casas.id_torre == Torre.id)
            facturas = facturas.filter(Torre.nombre.ilike(f"%{torre}%"))
            facturas = facturas.join(Apartamento, Casas.id_apartamento == Apartamento.id)
            facturas = facturas.filter(Apartamento.numero.ilike(f"%{apto}%"))
        except ValueError:
            # Si el formato no es válido, no aplica el filtro
            pass
    facturas = facturas.all()

    return render_template('facturacion/admin_facturas.html', facturas=facturas, torres=torres, apartamentos=apartamentos)

@admin_factura_bp.route('/facturas_usuario/<int:id>/<int:d>', methods=['GET'])
@login_required
@require_permission('Ver Facturacion')
def listar_historico(id,d):
    facturas = Factura.query.filter_by(id=id).first()
    historial = HistoricoFacturacion.query.filter_by(id_factura=id).order_by(HistoricoFacturacion.fecha_pago.asc()).all()
    registrar_log(current_user.id,"Facturacion", "Lista facturacion")
    return render_template('facturacion/admin_historico_factura_individual.html', historial=historial, factura=facturas, d=d)



@admin_factura_bp.route('/historico_facturas', methods=['GET', 'POST'])
@login_required
@require_permission('Historico Facturacion')
def historico_facturas():

    #unidades = Casas.query.all()
    unidades = (
    db.session.query(Torre.nombre, Apartamento.numero)
    .select_from(Casas)
    .join(Torre, Casas.id_torre == Torre.id)
    .join(Apartamento, Casas.id_apartamento == Apartamento.id)
    .join(Usuarios, Usuarios.id_casa == Casas.id)
    .distinct()
    .all()
)
    años = db.session.query(Factura.year).distinct().order_by(Factura.year.desc()).all()
    estados = db.session.query(Factura.estado).distinct().all()
    meses = [(i, datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)]

    filtros = {
        "unidad": request.args.get('unidad'),
        "año": request.args.get('año'),
        "estado": request.args.get('estado'),
        "mes": request.args.get('mes')
    }

    facturas = Factura.query.select_from(Factura).join(Usuarios, Factura.usuario_rel)

    if filtros["unidad"]:
        torre, apto = filtros["unidad"].split('-')
        facturas = facturas \
            .join(Casas, Usuarios.casa) \
            .join(Torre, Casas.torre) \
            .join(Apartamento, Casas.apartamento) \
            .filter(Torre.nombre == torre.strip(), Apartamento.numero == apto.strip())

    if filtros["año"]:
        facturas = facturas.filter(Factura.year == int(filtros["año"]))

    if filtros["estado"]:
        facturas = facturas.filter(Factura.estado == filtros["estado"])

    if filtros["mes"]:
        facturas = facturas.filter(Factura.mes == int(filtros["mes"]))

    facturas = facturas.order_by(Factura.year.desc(), Factura.mes.desc()).all()

    registrar_log(current_user.id, "Admin Facturacion", "Visualiza Historico de Facturas")

    exportar = request.args.get('exportar')
    
    if exportar == 'excel':
        return generar_excel_facturas(facturas)
    elif exportar == 'pdf':
        return generar_pdf_facturas(facturas)

    return render_template(
        'facturacion/admin_historico_facturas.html',
        facturas=facturas,
        unidades=unidades,
        años=[a.year for a in años],
        estados=[e.estado for e in estados],
        meses=meses,
        filtros=filtros
    )


from flask import make_response
import io
import pandas as pd
from xhtml2pdf import pisa
from flask import render_template_string

@require_permission('Generar Reportes')
def generar_excel_facturas(facturas):
    datos_conjunto = DatosConjunto.query.first()
    nombre_conjunto = datos_conjunto.nombre if datos_conjunto else "Conjunto Residencial"
    usuario=current_user.nombre
    fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    data = [{
        'Usuario': f.usuario_rel.nombre,
        'Unidad': f"{f.usuario_rel.casa.torre.nombre} - {f.usuario_rel.casa.apartamento.numero}",
        'Mes': f.mes,
        'Año': f.year,
        'Fecha de Pago': f.fecha_subio_pago.strftime('%d-%m-%Y') if f.fecha_subio_pago else 'No registrado',
        'Estado': f.estado
    } for f in facturas]

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet('Facturas')
        writer.sheets['Facturas'] = worksheet

        # Estilos
        bold = workbook.add_format({'bold': True})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1})
        center = workbook.add_format({'align': 'center'})

        # Logo
        logo_path = os.path.abspath(os.path.join("static", "img", "logo.png"))
        if os.path.exists(logo_path):
            worksheet.insert_image('A1', logo_path, {'x_scale': 0.4, 'y_scale': 0.4})

        # Título y datos del conjunto
        worksheet.write('C2', nombre_conjunto, bold)
        worksheet.write('C3', 'REPORTE DE HISTÓRICO DE FACTURAS', bold)
        worksheet.write('C4', f"Generado por: {usuario}", center)
        worksheet.write('C5', f"Fecha de generación: {fecha_actual}", center)

        # Escribir encabezados desde fila 7
        start_row = 6
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(start_row, col_num, value, header_format)

        # Escribir los datos
        for row_num, row_data in enumerate(df.values.tolist(), start=start_row + 1):
            for col_num, cell_data in enumerate(row_data):
                worksheet.write(row_num, col_num, cell_data)

        worksheet.set_column(0, len(df.columns) - 1, 20)

    output.seek(0)
    filename = f'historico_facturas_{datetime.now().strftime("%Y%m%d")}.xlsx'
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)


@require_permission('Generar Reportes')
def generar_pdf_facturas(facturas):
    datos_conjunto = DatosConjunto.query.first()
    nombre_conjunto = datos_conjunto.nombre if datos_conjunto else "Conjunto Residencial"

    fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M:%S')


 
    html = render_template_string("""
    <html>
    <head>
        <style>
            h1 { text-align: center; font-family: Helvetica; }
            h2 { text-align: center; font-family: Helvetica; }
            table { width: 100%; border-collapse: collapse; font-family: Helvetica; }
            th, td { border: 1px solid #000; padding: 5px; text-align: center; }
            .info { margin-bottom: 20px; font-family: Helvetica; }
            .logo { text-align: center; }
        </style>
    </head>
    <body>
        <div class="logo">
            <img src="{{ logo_path }}" width="120" height="80">
        </div>
        <h1>{{ nombre_conjunto }}</h1>
        <h2>REPORTE DE HISTÓRICO DE FACTURAS</h2>

        <div class="info">
            <p><strong>Generado por:</strong> {{ usuario }}</p>
            <p><strong>Fecha de generación:</strong> {{ fecha_actual }}</p>
        </div>

        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Usuario</th>
                    <th>Unidad</th>
                    <th>Mes - Año</th>
                    <th>Fecha de Pago</th>
                    <th>Estado</th>
                </tr>
            </thead>
            <tbody>
            {% for f in facturas %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ f.usuario_rel.nombre }}</td>
                    <td>{{ f.usuario_rel.casa.torre.nombre }} - {{ f.usuario_rel.casa.apartamento.numero }}</td>
                    <td>{{ f.mes }} - {{ f.year }}</td>
                    <td>{{ f.fecha_subio_pago.strftime('%d-%m-%Y') if f.fecha_subio_pago else 'No registrado' }}</td>
                    <td>{{ f.estado }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """, facturas=facturas, usuario=current_user.nombre, fecha_actual=fecha_actual,
       nombre_conjunto=nombre_conjunto,
       logo_path=os.path.abspath(os.path.join("static", "img", "logo.png")))

    output = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=output)
    output.seek(0)

    filename = f'historico_facturas_{datetime.now().strftime("%Y%m%d")}.pdf'
    return send_file(output, mimetype='application/pdf',
                     as_attachment=True, download_name=filename)

@admin_factura_bp.route('/exportar_facturas')
@login_required
@require_permission('Generar Reportes')
def exportar_facturas():
    from io import BytesIO
    import pandas as pd
    from flask import send_file
    from fpdf import FPDF

    # Obtener filtros
    torre = request.args.get('torre')
    year = request.args.get('year')
    estado = request.args.get('estado')
    formato = request.args.get('formato')

    query = Factura.query.join(Usuarios, Factura.usuario_id == Usuarios.id)\
                         .join(Casas, Usuarios.id_casa == Casas.id)\
                         .join(Torre, Casas.id_torre == Torre.id)\
                         .filter(Factura.estado != "Pendiente")

    if torre:
        query = query.filter(Torre.nombre == torre)
    if year:
        query = query.filter(Factura.year == int(year))
    if estado:
        query = query.filter(Factura.estado == estado)

    facturas = query.all()

    data = [{
        "Usuario": f.usuario_rel.nombre,
        "Torre": f.usuario_rel.casa.torre.nombre,
        "Apartamento": f.usuario_rel.casa.apartamento.numero,
        "Mes": f.mes,
        "Año": f.year,
        "Estado": f.estado,
        "Fecha de Pago": f.fecha_subio_pago.strftime('%d-%m-%Y') if f.fecha_subio_pago else "No registrado"
    } for f in facturas]

    if formato == "excel":
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Facturas', index=False)
        output.seek(0)
        return send_file(output, download_name="historico_facturas.xlsx", as_attachment=True)

    elif formato == "pdf":
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, "Histórico de Facturas", ln=True, align='C')

        # Encabezado
        encabezados = ["Usuario", "Torre", "Apartamento", "Mes", "Año", "Estado", "Fecha de Pago"]
        for col in encabezados:
            pdf.cell(40, 10, col, border=1)

        pdf.ln()
        for fila in data:
            for col in encabezados:
                texto = str(fila[col])
                pdf.cell(40, 10, texto, border=1)
            pdf.ln()

        output = BytesIO()
        pdf.output(output)
        output.seek(0)
        return send_file(output, download_name="historico_facturas.pdf", as_attachment=True)

    else:
        flash("Formato no válido", "danger")
        return redirect(url_for('admin_factura_bp.historico_facturas'))


@admin_factura_bp.route('/aprobar_pago/<int:factura_id>', methods=['GET','POST'])
@login_required
@require_permission('Aprobar Pagos')
def aprobar_pago(factura_id):
    """Aprueba el pago de una factura y cambia su estado a 'Aprobado'."""
    #facturaH = HistoricoFacturacion.query.get_or_404(factura_id)
    factura = Factura.query.get_or_404(factura_id)

    facturaH = HistoricoFacturacion.query.filter_by(id_factura=factura_id, estado="En espera de comprobación").first()
    nota_admin = request.form['nota']

    if not facturaH:
        flash("No se encontró un pago pendiente para esta factura.", "danger")
        return redirect(url_for('admin_facturacion.admin_facturas'))

    
    if facturaH.estado == "Aprobado":
        flash("El pago ya fue aprobado anteriormente.", "info")
    else:     
        facturaH.estado = "Aprobado"
        facturaH.nota = nota_admin
        factura.total -= float(facturaH.monto_pagado)
        if factura.abono is None:
            factura.abono = 0  # Inicializa abono en 0 si es None
        factura.abono += float(facturaH.monto_pagado)
        db.session.commit()

        datos = {
            'usuario': facturaH.usuario.nombre,
            'factura': facturaH.consecutivo_pago,
            'valor': facturaH.monto_pagado,
            'mes': facturaH.factura.mes,
            'año': facturaH.factura.year,
            'nota': facturaH.nota,
            'estado': facturaH.estado
        }
        enviar_notificacion(
            destinatario=facturaH.usuario.email,
            asunto='Factura Aprobada',
            tipo_accion='factura_aprobada',
            datos=datos
        )
        

        if factura.total <= 0:
            factura.estado = "Pagada"
            factura.fecha_subido_pago = datetime.today()
            db.session.commit()
            datos = {
            'usuario': factura.usuario_rel.nombre,
            'mes': factura.mes,
            'año': factura.year,
            'estado': factura.estado
            }
            enviar_notificacion(
            destinatario=factura.usuario_rel.email,
            asunto='Factura Pagada',
            tipo_accion='factura_padaga',
            datos=datos
            )

            
        registrar_log(current_user.id,"Admin Facturacion", "Aprobó el pago de la factura "+str(factura_id))
        flash("Pago aprobado con éxito.", "success")

    return redirect(url_for('admin_facturacion.listar_historico', id=factura.usuario_id, d=0))


@admin_factura_bp.route('/rechazar_pago/<int:factura_id>', methods=['GET','POST'])
@login_required
@require_permission('Rechazar Pagos')
def rechazar_pago(factura_id):
    """Rechaza el pago de una factura y cambia su estado a 'Rechazado'."""
    factura = Factura.query.get_or_404(factura_id)
    config = ConfiguracionFactura.query.first()
    facturaH = HistoricoFacturacion.query.filter_by(id_factura=factura_id, estado="En espera de comprobación").first()
    nota_admin = request.form['nota']
    

    if facturaH.estado== "Rechazado":
        flash("El pago ya fue rechazado anteriormente.", "info")
    else:
        facturaH.estado = "Rechazado"
        facturaH.nota = nota_admin
        db.session.commit()

        datos = {
            'usuario': facturaH.usuario.nombre,
            'factura': facturaH.consecutivo_pago,
            'valor': facturaH.monto_pagado,
            'mes': facturaH.factura.mes,
            'año': facturaH.factura.year,
            'nota': facturaH.nota,
            'estado': facturaH.estado
        }
        enviar_notificacion(
            destinatario=facturaH.usuario.email,
            asunto='Factura Rechazada',
            tipo_accion='factura_rechada',
            datos=datos
        )
        registrar_log(current_user.id,"Admin Facturacion", "Rechazó el pago de la factura "+str(factura_id))
        flash("Pago rechazado. El usuario debe subir un nuevo comprobante.", "warning")

    return redirect(url_for('admin_facturacion.listar_historico', id=factura.usuario_id, d=0))

@admin_factura_bp.route('/facturas/ver_comprobante/<int:id>')
@login_required
@require_permission('Descargar Comprobantes Facturacion')
def ver_comprobante1(id):
    factura = HistoricoFacturacion.query.get_or_404(id)
    archivo = factura.comprobante_encriptado
    

    if not archivo:
        flash("Comprobante no encontrado para esta factura.", "danger")
        return redirect(url_for('admin_facturacion.admin_facturas'))

    # Registrar actividad
    registrar_log(current_user.id,"Admin Facturacion", "Descarga comprobante subido - factura ID: "+str(factura.id_factura))

    # Ruta base fuera de la carpeta app
    base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    carpeta_comprobantes = os.path.join(base_dir, 'static', 'facturacion', 'comprobantes', f'usuario_{factura.id_usuario}')
    ruta_archivo = os.path.join(carpeta_comprobantes, archivo)

    # Validar existencia del archivo
    if not os.path.isfile(ruta_archivo):
        flash("El archivo del comprobante no existe en el servidor.", "danger")
        return redirect(url_for('admin_facturacion.admin_facturas'))

    # Enviar archivo como respuesta
    return send_from_directory(carpeta_comprobantes, archivo)


def generar_facturas_al_ingresar():
    """Genera facturas para todos los usuarios con rol Residente si aún no se han generado este mes."""
    config = ConfiguracionFactura.query.first()
    if not config:
        return "No hay configuración de facturación."

    hoy = datetime.today()
    año, mes = hoy.year, hoy.month

    # Obtener todos los residentes
    residentes = Usuarios.query.filter_by(id_rol=1).all()  # Ajusta el ID del rol "Residente"

    for usuario in residentes:
        # Verificar si ya existe una factura para este usuario en el mes actual
        factura_existente = Factura.query.filter_by(usuario_id=usuario.id, year=año, mes=mes).first()
        if factura_existente:
            continue  # Si ya existe, no la generamos de nuevo

        # Calcular el monto según si hay mora
        mora = 0
        ultima_factura_pendiente = Factura.query.filter_by(usuario_id=usuario.id, estado="Pendiente").order_by(Factura.year.desc(), Factura.mes.desc()).first()
        configuracion = ConfiguracionFactura.query.first()
        dia_habil_pago = configuracion.dia_habil_pago if configuracion else 10  

        if mes == 12:
            fecha_max_pago = date((año+1), 1, min(dia_habil_pago, 28)) 
        else:
            fecha_max_pago = date(año, (mes+1), min(dia_habil_pago, 28)) 

        if ultima_factura_pendiente:
            mora = float(config.tasa_mora or 0) * ultima_factura_pendiente.total  # Aplica interés de mora

        saldo_anterior = ultima_factura_pendiente.total if ultima_factura_pendiente else 0
        descuento_pago = float(mora) * float(config.tasa_descuento or 0)
        nuevo_monto = ((float(config.tarifa or 0) + float(mora or 0)+ saldo_anterior) - float(descuento_pago or 0)) 

        # Crear la nueva factura
        nueva_factura = Factura(
            usuario_id=usuario.id,
            year=año,
            mes=mes,
            fecha_emision=date.today(),
            fecha_max_pago=fecha_max_pago,
            valor_base=configuracion.tarifa,
            mora=mora,
            descuento=descuento_pago,
            saldo_anterior=saldo_anterior,
            total=nuevo_monto,
            validacion=nuevo_monto,
            estado="Pendiente"
        )
        db.session.add(nueva_factura)


        datos = {
            'usuario': usuario.nombre,
            'mes': mes,
            'año': año,
            'valor': nuevo_monto,
            'fecha_max_pago': fecha_max_pago.strftime('%d/%m/%Y'),
        }
        enviar_notificacion(
            destinatario=usuario.email,
            asunto='Factura Generada',
            tipo_accion='factura_generada',
            datos=datos
        )


    db.session.commit()
    return "Facturas generadas correctamente."