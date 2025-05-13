from flask import Blueprint, render_template, request, redirect, url_for, flash,  session
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app import db
from models.usuario import Usuarios
from models.casas import Casas, Apartamento, Torre
from models.roles import Roles
from controllers.configuracion import require_permission
from controllers.log import registrar_log

usuarios_bp = Blueprint("usuarios", __name__)

# Mostrar lista de usuarios
@usuarios_bp.route("/usuarios")
@login_required
@require_permission('Administrar Usuarios')
def listar_usuarios():
    #usuarios = Usuarios.query.all()
    usuarios = Usuarios.query.filter(Usuarios.id != 4).all()
    #roles = Roles.query.all()
    roles = Roles.query.filter(Roles.id != 99).all()
    torres = Torre.query.all()
    apartamentos = Apartamento.query.all()
    
    registrar_log(current_user.id,"Usuarios", "Visualiza Lista Usuarios")
    return render_template("usuarios/usuarios.html", usuarios=usuarios, roles=roles, torres=torres, apartamentos=apartamentos)

# Editar usuario
@usuarios_bp.route("/editar_usuario/<int:id>", methods=["GET", "POST"])
@login_required
@require_permission('Modificar Usuario')
def editar_usuario(id):
    usuario = Usuarios.query.get_or_404(id)
    roles = Roles.query.filter(Roles.id != 5).all()
    casas = Casas.query.all()
    torres = Torre.query.all()
    apartamentos = Apartamento.query.all()

    if request.method == "POST":
        usuario.nombre = request.form["nombre"]
        usuario.identificacion = request.form["identificacion"]
        usuario.email = request.form["email"]
        usuario.telefono = request.form["telefono"]
        usuario.id_rol = request.form["id_rol"]


       # Obtener la casa seleccionada según la torre y apartamento elegidos
        id_torre = request.form.get('id_torre')
        id_apartamento = request.form.get('id_apartamento')

        casa = Casas.query.filter_by(id_torre=id_torre, id_apartamento=id_apartamento).first()
        
        if not casa:
            flash("No se encontró una casa con la torre y apartamento seleccionados.", "danger")
            return redirect(url_for('usuarios.editar_usuario', id=id))

        usuario.id_casa = casa.id  # Guardamos solo el id de la casa

        nueva_contraseña = request.form['contraseña']
        if nueva_contraseña:
            usuario.contraseña = generate_password_hash(nueva_contraseña)

        db.session.commit()

        registrar_log(current_user.id, "Usuarios","Edita Usuario")

        flash("Usuario actualizado correctamente.", "success")
        return redirect(url_for("usuarios.listar_usuarios"))

    return render_template("usuarios/editar_usuario.html", usuario=usuario, roles=roles, casas=casas, torres=torres, apartamentos=apartamentos)

# Eliminar usuario
@usuarios_bp.route("/eliminar_usuario/<int:id>", methods=["POST"])
@login_required
@require_permission('Administrar Usuarios')
def eliminar_usuario(id):
    usuario = Usuarios.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()

    registrar_log(current_user.id,"Usuarios", "Elimina Usuario")
    flash("Usuario eliminado correctamente.", "success")
    return redirect(url_for("usuarios.listar_usuarios"))

# inhabilitar usuario
@usuarios_bp.route("/inhabilitar/<int:id>", methods=["POST"])
@login_required
@require_permission('Inhabilitar Usuario')
def inhabilitar(id):
    usuario = Usuarios.query.get_or_404(id)
    usuario.estado=2
    db.session.commit()
    registrar_log(current_user.id,"Usuarios", "Inhabilita Usuario")
    flash("Usuario Inhabilitado correctamente.", "success")
    return redirect(url_for("usuarios.listar_usuarios"))

# habilitar usuario
@usuarios_bp.route("/habilitar/<int:id>", methods=["POST"])
@login_required
@require_permission('Habilitar Usuario')
def habilitar(id):
    usuario = Usuarios.query.get_or_404(id)
    usuario.estado=1
    db.session.commit()
    registrar_log(current_user.id,"Usuarios", "Habilita Usuario")
    flash("Usuario Habilitado correctamente.", "success")
    return redirect(url_for("usuarios.listar_usuarios"))



@usuarios_bp.route('/editar_datos/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_datos(id):
    # Obtener el usuario actual desde la sesión

    usuario = Usuarios.query.get_or_404(id)

    if request.method == 'POST':

        email = request.form.get('email')
        telefono = request.form.get('telefono')
        nueva_contraseña = request.form.get('contraseña')

        # Validar campos
        if not email:
            flash('Nombre y email son obligatorios.', 'danger')
            return redirect(url_for('usuarios.editar_datos'))


        usuario.email = email
        usuario.telefono = telefono

        if nueva_contraseña and nueva_contraseña.strip() != '':
            usuario.contraseña = generate_password_hash(nueva_contraseña)

        try:
            registrar_log(current_user.id,"Usuarios", "Edita Datos Usuario")
            db.session.commit()
            flash('✅ Tus datos fueron actualizados correctamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Ocurrió un error: {str(e)}', 'danger')

        return redirect(url_for('usuarios.editar_datos'))

    return render_template('usuarios/cambiar_datos_usuario.html', usuario=usuario)
