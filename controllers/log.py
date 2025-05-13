from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from app import db
from models.log import LogActividad
from models.usuario import Usuarios
from models.casas import Apartamento, Torre, Casas
from models.roles import Roles
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import pandas as pd

log_bp = Blueprint('log', __name__)

def registrar_log(id_usuario, tipo, accion):
    ip_usuario = request.remote_addr  # Captura la IP del usuario
    log = LogActividad(id_usuario=id_usuario, accion=accion,tipo=tipo, ip=ip_usuario)
    db.session.add(log)
    db.session.commit()



@log_bp.route('/logs', methods=['GET'])
@login_required
def listar_usuarios_logs():
    from controllers.configuracion import require_permission
    require_permission('Ver Logs')
    
    # Obtener parámetros de filtro (si existen)
    nombre = request.args.get('nombre', '').strip()
    torre_id = request.args.get('torre', '').strip()
    apartamento_num = request.args.get('apartamento', '').strip()  # Cambiado el nombre para evitar conflicto
    rol_id = request.args.get('rol', '').strip()

    # Consulta base
    query = Usuarios.query

    # Aplicar filtros
    if nombre:
        query = query.filter(Usuarios.nombre.ilike(f'%{nombre}%'))
    
    if torre_id:
        query = query.join(Usuarios.casa).filter(Casas.id_torre == torre_id)  # Asumiendo que hay una relación con Casa
    
    if apartamento_num:
        query = query.join(Usuarios.casa).filter(Casas.id_apartamento == apartamento_num)
    
    if rol_id:
        query = query.filter(Usuarios.id_rol == rol_id)

    # Obtener datos para los selects (torres, apartamentos y roles)
    torres = Torre.query.all()
    apartamentos = Apartamento.query.all()  # Variable renombrada
    #roles = Roles.query.all()
    roles = Roles.query.filter(Roles.id != 99).all()


    # Ejecutar consulta final
    usuarios = query.filter(Usuarios.id != 4).all()

    registrar_log(current_user.id,"Auditoria", "Lista Usuarios Logs")

    return render_template(
        'log/listar_usuarios_logs.html',
        usuarios=usuarios,
        torres=torres,
        roles=roles, 
        apartamentos=apartamentos,  # Variable renombrada
        filtros={
            'nombre': nombre,
            'torre': torre_id,
            'apartamento': apartamento_num,
            'rol': rol_id
        }
    )
    usuarios = Usuarios.query.all()
    return render_template('log/listar_usuarios_logs.html', usuarios=usuarios)


@log_bp.route('/logs/usuario/<int:id_usuario>', methods=['GET'])
@login_required

def ver_logs_usuario(id_usuario):
    from controllers.configuracion import require_permission
    require_permission('Ver Logs')

    # Obtener parámetros de filtro
    tipo = request.args.get('tipo', '').strip()
    fecha_inicio = request.args.get('fecha_inicio', '').strip()
    fecha_fin = request.args.get('fecha_fin', '').strip()
    
    # Obtener usuario
    usuario = Usuarios.query.get_or_404(id_usuario)
    
    # Consulta base
    query = LogActividad.query.filter_by(id_usuario=id_usuario)
    
    # Aplicar filtros
    if tipo:
        query = query.filter(LogActividad.tipo.ilike(f'%{tipo}%'))
    
    if fecha_inicio:
        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            query = query.filter(LogActividad.fecha >= fecha_inicio_dt)
        except ValueError:
            pass
    
    if fecha_fin:
        try:
            fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(LogActividad.fecha < fecha_fin_dt)
        except ValueError:
            pass
    
    # Ordenar por fecha descendente
    logs = query.order_by(LogActividad.fecha.desc()).all()
    
    # Obtener tipos únicos para el dropdown
    tipos_logs = db.session.query(LogActividad.tipo).distinct().all()
    tipos_logs = [t[0] for t in tipos_logs]

    registrar_log(current_user.id,"Auditoria", "Ver Log x Usuario id: "+str(usuario.id))
    
    return render_template(
        'log/logs_usuario.html',
        usuario=usuario,
        logs=logs,
        tipos_logs=tipos_logs,
        filtros={
            'tipo': tipo,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin
        }
    )


    usuario = Usuarios.query.get_or_404(id_usuario)
    logs = LogActividad.query.filter_by(id_usuario=id_usuario).order_by(LogActividad.fecha.desc()).all()
    
    return render_template('log/logs_usuario.html', usuario=usuario, logs=logs)



@log_bp.route('/log/<int:id_usuario>/descargar', methods=['GET'])
def descargar_logs_usuario(id_usuario):
    tipo = request.args.get("tipo")
    fecha_inicio = request.args.get("fecha_inicio")
    fecha_fin = request.args.get("fecha_fin")
    formato = request.args.get("formato", "pdf")

    query = LogActividad.query.filter_by(id_usuario=id_usuario)

    if tipo:
        query = query.filter_by(tipo=tipo)

    if fecha_inicio:
        fecha_inicio_dt = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        query = query.filter(LogActividad.fecha >= fecha_inicio_dt)

    if fecha_fin:
        fecha_fin_dt = datetime.strptime(fecha_fin, "%Y-%m-%d")
        query = query.filter(LogActividad.fecha <= fecha_fin_dt)

    logs = query.order_by(LogActividad.fecha.desc()).all()
    usuario = Usuarios.query.get(id_usuario)
    fecha_actual = datetime.now().strftime("%Y-%m-%d")


    if formato == "excel":
        # Exportar a Excel usando pandas
        data = [{
            "ID": log.id,
            "Tipo": log.tipo,
            "Acción": log.accion,
            "Fecha": log.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            "IP": log.ip
        } for log in logs]

        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Logs')

        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"Historial_Usuario_{usuario.nombre}_{fecha_actual}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        # Exportar a PDF usando ReportLab
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2, height - 40, f"Historial de Actividad - {usuario.nombre}")

        c.setFont("Helvetica", 10)
        y = height - 70

        for log in logs:
            log_text = f"{log.fecha.strftime('%Y-%m-%d %H:%M:%S')} | {log.tipo} | {log.accion} | IP: {log.ip}"
            c.drawString(40, y, log_text)
            y -= 15
            if y < 40:
                c.showPage()
                y = height - 50

        if not logs:
            c.drawString(40, y, "No se encontraron registros con los filtros seleccionados.")

        c.save()
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"Historial_Usuario_{usuario.nombre}_{fecha_actual}.pdf",
            mimetype="application/pdf"
        )