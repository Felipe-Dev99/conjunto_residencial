from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app, session
from flask_login import login_required, current_user
from datetime import datetime
from werkzeug.utils import secure_filename
from app import db
from models.pqrs import PQRS, estados_pqrs, descripcion_pqrs, tipo_pqrs, HistorialPQRS, PQRSArchivo
from models.roles import Roles, RolPermiso, Permisos
from models.usuario import Usuarios
from datetime import datetime, time, timedelta
import io
import os
from controllers.configuracion import require_permission
from controllers.log import registrar_log, LogActividad
from sqlalchemy import not_
from controllers.api_mail import enviar_notificacion

admin_pqrs_bp = Blueprint('admin_pqrs', __name__)


@admin_pqrs_bp.route('/pqrs')
@login_required
@require_permission('Ver PQRS')
def listar():
    """Mostrar las PQRS según los permisos del usuario."""
    
    # Verificar si el usuario tiene permiso para ver todas las PQRS
    permiso_admin = db.session.query(RolPermiso).join(Permisos, RolPermiso.permiso_id == Permisos.id).filter(
    RolPermiso.rol_id == current_user.id_rol,
    Permisos.nombre == "Asignar PQRS"
    ).first()

    # Si tiene permiso, puede ver todas las PQRS; si no, solo las asignadas a él
    query = PQRS.query if permiso_admin else PQRS.query.filter_by(id_asistente=current_user.id)

    # Aplicar filtros
    formulario = request.args.get('formulario')
    estado = request.args.get('estado')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    numero_atencion = request.args.get('numero_atencion')

    if formulario:
        query = query.filter(PQRS.id_tipo == formulario)
    if estado:
        query = query.filter(PQRS.id_estado == estado)
    if fecha_inicio and fecha_fin:
        query = query.filter(PQRS.fecha_creacion.between(fecha_inicio, fecha_fin))
    if numero_atencion:
        query = query.filter(PQRS.numero_radicado == numero_atencion)

    # Ordenar por fecha de creación
    query = query.order_by(PQRS.fecha_creacion.desc())

    # Paginación
    page = request.args.get('page', 1, type=int)  # Página actual (por defecto 1)
    per_page = 5  # Número de registros por página
    pqrs_paginados = query.paginate(page=page, per_page=per_page, error_out=False)

    # Registrar en el log la acción
    registrar_log(current_user.id,"Admin PQRS", "Lista todas Pqrs")

    # Renderizar template con la lista filtrada y paginada
    return render_template('pqrs/admin_listar_pqrs.html', 
                           pqrs_list=pqrs_paginados.items,  # Solo los elementos de la página actual
                           pqrs_paginados=pqrs_paginados,
                           formulario=formulario, 
                           estado_filtro=estado,
                           fecha_inicio=fecha_inicio,
                           fecha_fin=fecha_fin,
                           numero_atencion=numero_atencion)

@admin_pqrs_bp.route('/responder_pqrs/<int:id>', methods=['GET', 'POST'])
@login_required
@require_permission('Responder PQRS')
def responder_pqrs(id):
    # Buscar la PQRS por ID
    pqrs = PQRS.query.get_or_404(id)
    
    # Solo permitir respuesta si la PQRS está pendiente
    if pqrs.id_estado == 3:  # Estado 1: "Registrada"
        flash('Esta PQRS ya ha sido respondida.', 'warning')
        return redirect(url_for('admin_pqrs.listar'))
    
    if request.method == 'POST':
        respuesta = request.form.get('respuesta')
        if not respuesta:
            flash('Debe ingresar una respuesta.', 'danger')
        else:
            # Guardar respuesta y actualizar estado
            estado_anterior = pqrs.id_estado

            pqrs.respuesta = respuesta
            pqrs.fecha_respuesta = datetime.now()
            pqrs.id_estado = request.form.get('estado')  # Estado 2: "En Proceso" o "Finalizada"
            
            # Guardar en el historial
            nuevo_historial = HistorialPQRS(
                id_pqrs=id,
                respuesta=respuesta,
                id_usuario=current_user.id,
                estado_anterior=estado_anterior,
                estado_actual=pqrs.id_estado
            )
            db.session.add(nuevo_historial)

            db.session.commit()

            if pqrs.id_estado == 3: 
                asunto= 'PQRS Resuelta Definitiva'
            else:   
                asunto= 'PQRS Respuesta' # Estado 3: "Finalizada"

            datos = {
                'usuario': pqrs.usuario.nombre,
                'radicado': pqrs.numero_radicado,
                'tipop': pqrs.tipo_p.nombre,
                'respuesta': pqrs.respuesta,
                'fecha_respuesta': pqrs.fecha_respuestapuesta.strftime("%Y-%m-%d %H:%M:%S"),
                'estado': pqrs.estado.nombre,
                }
            enviar_notificacion(
                destinatario=pqrs.usuario.email,
                asunto=asunto,
                tipo_accion='pqrs_respuesta',
                datos=datos
                )

            registrar_log(current_user.id,"Admin PQRS", "Responde Pqrs id "+str(pqrs.id))
            flash('La PQRS ha sido respondida correctamente.', 'success')
            return redirect(url_for('admin_pqrs.listar'))
        
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
            "usuario": item.usuario.nombre if item.usuario else "Desconocido",
            "estado_anterior": ESTADOS.get(item.estado_anterior, "Desconocido"),
            "estado_actual": ESTADOS.get(item.estado_actual, "Desconocido"),
        })

    estados = estados_pqrs.query.filter(estados_pqrs.id.notin_([1, 4])).order_by(estados_pqrs.id.asc()).all()
    archivos = PQRSArchivo.query.filter_by(id_pqrs=id).all()
    return render_template('pqrs/responder_pqrs.html', pqrs=pqrs, estados=estados, historial=historial_traducido, archivos=archivos)

@admin_pqrs_bp.route('/descargar_archivo/<int:id_archivo>')
@login_required
@require_permission('Responder PQRS')
def descargar_archivo(id_archivo):
    archivo = PQRSArchivo.query.get_or_404(id_archivo)

    # Subir un nivel desde app para encontrar static/
    base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    ruta_archivo = os.path.join(base_dir, 'static', 'pqrs', str(archivo.id_pqrs), archivo.nombre_encriptado)

    if not os.path.exists(ruta_archivo):
        flash("El archivo no existe en el servidor.", "danger")
        return redirect(url_for('pqrs.ver_pqrs', id=archivo.id_pqrs))

    registrar_log(current_user.id,"Admin PQRS", "Descarga archivo "+str(archivo.nombre_original)+" de la PQRS id "+str(archivo.id_pqrs))
    
    return send_file(
        ruta_archivo,
        as_attachment=True,
        download_name=archivo.nombre_original
    )


@admin_pqrs_bp.route('/pqrs/asignar/<int:id>', methods=['GET', 'POST'])
@login_required
@require_permission('Asignar PQRS')
def asignar_pqrs(id):
    pqrs = PQRS.query.get_or_404(id)
    asistentes = (
        Usuarios.query
        .join(RolPermiso, RolPermiso.rol_id == Usuarios.id_rol)  # Relación con el rol del usuario
        .join(Permisos, RolPermiso.permiso_id == Permisos.id)  # Relación con los permisos
        .filter(Permisos.nombre == 'Responder PQRS')  # Filtrar solo asistentes con este permiso
        .filter(Usuarios.id_rol != 99)  # Excluir usuarios con rol Root
        .all()
    )

    if request.method == 'POST':
        id_asistente = request.form.get('id_asistente')
        if not id_asistente:
            flash("Debe seleccionar un asistente.", "danger")
            return redirect(url_for('admin_pqrs.asignar_pqrs', id=id))
        
        estado_anterior = pqrs.id_estado
        
                    # Guardar en el historial
        nuevo_historial = HistorialPQRS(
            id_pqrs=id,
            respuesta="Asignada a asistente",
            id_usuario=current_user.id,
            estado_anterior=estado_anterior,
            estado_actual=2
        )
        db.session.add(nuevo_historial)

        pqrs.id_estado = 2
        pqrs.id_asistente = id_asistente
        db.session.commit()

        datos = {
            'usuario': pqrs.usuario.nombre,
            'radicado': pqrs.numero_radicado,
            'tipop': pqrs.tipo_p.nombre,
            'estado': pqrs.estado.nombre,
            }
        enviar_notificacion(
            destinatario=pqrs.usuario.email,
            asunto='Notificación de Asignación de PQRS',
            tipo_accion='pqrs_asignada',
            datos=datos
            )
        flash("PQRS asignada correctamente.", "success")
        registrar_log(current_user.id,"Admin PQRS", "PQRS Asignada a "+str(pqrs.usuario.nombre)+" Rol: "+str(pqrs.usuario.rol.nombre))
    
        return redirect(url_for('admin_pqrs.responder_pqrs', id=id))

    return render_template('pqrs/asignar.html', pqrs=pqrs, asistentes=asistentes)




def validar_estado_pqrs():
    if not current_user.is_authenticated:
        return

    hoy = datetime.now().date()
    pqrs_vencidas = PQRS.query.filter(PQRS.fecha_max < hoy, PQRS.id_estado != 4).all()

    for pqrs in pqrs_vencidas:
        pqrs.id_estado = 4  # Fuera de Tiempo
        db.session.add(pqrs)

        estado_anterior = pqrs.id_estado
            
                        # Guardar en el historial
        nuevo_historial = HistorialPQRS(
            id_pqrs=pqrs.id,
            respuesta="Se cierra PQRS por vencimiento",
            estado_anterior=estado_anterior,
            estado_actual=4
        )
        db.session.add(nuevo_historial)

        datos = {
            'usuario': pqrs.usuario.nombre,
            'radicado': pqrs.numero_radicado,
            'tipop': pqrs.tipo_p.nombre,
            'estado': 'Se cierra PQRS por vencimiento',
            }
        enviar_notificacion(
            destinatario=pqrs.usuario.email,
            asunto='Notificación PQRS',
            tipo_accion='pqrs_vencida',
            datos=datos
            )

    if pqrs_vencidas:
        db.session.commit()