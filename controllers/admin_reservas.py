from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, send_file, Response
from flask_login import login_required, current_user
from models.reserva import Reserva
from models.casas import Casas, Apartamento, Torre
from app import db
import os
from controllers.configuracion import require_permission
from controllers.log import registrar_log
from controllers.api_mail import enviar_notificacion


admin_reservas_bp = Blueprint('admin_reservas', __name__)

UPLOAD_FOLDER = 'static/comprobantes'  # Carpeta donde se guardan los comprobantes

@admin_reservas_bp.route('/reservas')
@require_permission('Ver Reservas')
@login_required
def listar_reservas_admin():
  
    registrar_log(current_user.id,"Admin Reservas", "Lista todas las reservas")
    reservas = Reserva.query.order_by(Reserva.numero_radicado.desc()).all()
    torre = Torre.query.all()
    apartamento = Apartamento.query.all()
    return render_template('reservas/listar_reservas.html', reservas=reservas, torres=torre, apartamentos=apartamento)

@admin_reservas_bp.route('/reserva/aprobar/<int:id>', methods=['POST'])
@login_required
@require_permission('Aprobar Reserva')
def aprobar_reserva(id):
    
    reserva = Reserva.query.get_or_404(id)
    reserva.id_estado = 2
    db.session.commit()

    datos = {
        'usuario': reserva.usuario.nombre,
        'radicado': reserva.numero_radicado,
        'fecha': reserva.fecha.strftime('%Y-%m-%d'),
        'hora': reserva.horario,
        'espacio': reserva.espacios.nombre,
        'estado': 'Aprobada',
        }
    enviar_notificacion(
        destinatario=reserva.usuario.email,
        asunto='Reserva Aprobada',
        tipo_accion='reserva_aprobada',
        datos=datos
        )

    registrar_log(current_user.id,"Admin Reservas", "Aprueba reserva id "+str(reserva.id))
    flash("Reserva aprobada correctamente.", "success")
    return redirect(url_for('admin_reservas.detalle_reserva', id=reserva.id ))

@admin_reservas_bp.route('/reserva/rechazar/<int:id>', methods=['POST'])
@require_permission('Rechazar Reserva')
def rechazar_reserva(id):
    reserva = Reserva.query.get_or_404(id)
    observacion = request.form['observacion']

    reserva.id_estado = 4
    reserva.observacion = observacion
    db.session.commit()

    datos = {
        'usuario': reserva.usuario.nombre,
        'radicado': reserva.numero_radicado,
        'fecha': reserva.fecha.strftime('%Y-%m-%d'),
        'hora': reserva.horario,
        'espacio': reserva.espacios.nombre,
        'observacion': observacion,
        'estado': 'Rechazada',
        }
    enviar_notificacion(
        destinatario=reserva.usuario.email,
        asunto='Reserva Rechazada',
        tipo_accion='reserva_rechazada',
        datos=datos
        )
    registrar_log(current_user.id,"Admin Reservas", "Rechaza reserva id "+str(reserva.id))
    flash('Reserva rechazada correctamente.', 'danger')
    return redirect(url_for('admin_reservas.detalle_reserva', id=id))


@admin_reservas_bp.route('/comprobante/<int:id>', methods=['POST','GET' ])
@login_required
@require_permission('Ver Reservas')
def ver_comprobante(id):
    if request.method == "GET":
        agenda = db.session.query(Reserva).filter_by(id=id).first()
        archivo = agenda.comprobante_path

        if not agenda or not agenda.comprobante_pago:
            flash('No hay comprobante disponible.', 'danger')
            return redirect(url_for('reserva.mis_agendas'))
        registrar_log(current_user.id,"Admin Reservas", "Descarga comprobante reserva id "+str(agenda.id))
         # Ruta relativa desde la carpeta 'static'
        carpeta_comprobantes = current_app.config['UPLOAD_FOLDER']      

        return send_from_directory(carpeta_comprobantes, archivo)



@admin_reservas_bp.route('/detalle/<int:id>')
@login_required
@require_permission('Ver Reservas')
def detalle_reserva(id):
    reserva = Reserva.query.get_or_404(id)
    registrar_log(current_user.id,"Admin Reservas", "Detalle Reserva id "+str(reserva.id))
    return render_template('reservas/ver_reserva.html', reserva=reserva)
