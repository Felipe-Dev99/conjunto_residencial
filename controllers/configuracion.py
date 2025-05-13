from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from functools import wraps
from app import db
import os
from models.roles import Roles, Permisos, RolPermiso
from models.casas import Casas, Apartamento, Torre
from models.pqrs import descripcion_pqrs, tipo_pqrs
from models.reserva import Espacios_reserva
from models.datos_conjunto import DatosConjunto
from controllers.log import registrar_log

config_bp = Blueprint('config', __name__)

""" def require_permission(permission_name):
    " Decorador para verificar si el usuario tiene un permiso específico. "
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Obtener los permisos del usuario
            permisos_usuario = db.session.query(Permisos.nombre).join(RolPermiso).filter(
            RolPermiso.rol_id == current_user.id_rol
            ).all()

            # Convertir los permisos en una lista de strings
            permisos_usuario = [permiso.nombre for permiso in permisos_usuario]

            # Verificar si el usuario tiene el permiso necesario
            if permission_name not in permisos_usuario:
                flash("No tienes permiso para acceder a esta función.", "danger")
                return redirect(url_for('main.no_autorizado'))  # Redirige a la página principal o de error

            return func(*args, **kwargs)
        return wrapper
    return decorator
 """

def require_permission(*permission_names):
    """
    Decorador para verificar si el usuario tiene al menos uno de los permisos especificados.
    Se puede usar como @require_permission("Permiso1", "Permiso2")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            permisos_usuario = db.session.query(Permisos.nombre).join(RolPermiso).filter(
                RolPermiso.rol_id == current_user.id_rol
            ).all()

            permisos_usuario = [permiso.nombre for permiso in permisos_usuario]

            # Verifica si el usuario tiene al menos uno de los permisos requeridos
            if not any(p in permisos_usuario for p in permission_names):
                flash("No tienes permiso para acceder a esta función.", "danger")
                return redirect(url_for('main.no_autorizado'))

            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_permission1(permission_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Debes iniciar sesión.", "danger")
                return redirect(url_for('main.login'))
            
            # Consultamos si el usuario tiene el permiso específico
            permiso = Permisos.query.filter_by(nombre=permission_name).first()
            if not permiso:
                flash("Permiso no encontrado.", "danger")
                return redirect(url_for('index'))
            
            tiene_permiso = RolPermiso.query.filter_by(rol_id=current_user.id_rol, permiso_id=permiso.id).first()
            if not tiene_permiso:
                flash("No tienes permisos para acceder a esta sección.", "danger")
                return redirect(url_for('index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

@config_bp.route('')
@login_required
@require_permission('Configuracion')
def configuracion():
    registrar_log(current_user.id,"Configuracion", "Visualiza opciones de configuracion") 
    return render_template('config/configuracion.html')

@config_bp.route("/datos_conjunto", methods=["GET", "POST"])
@login_required
@require_permission('Configuracion')
def gestionar_datos_conjunto():
    datos = DatosConjunto.query.first()  # Solo debe existir un registro
    if request.method == "POST":

        print(request.files)
                # Guardar archivos PDF
        base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        carpeta_config = os.path.join(base_dir, 'static', 'configuracion')
        os.makedirs(carpeta_config, exist_ok=True)

        terminos_pdf = request.files.get("terminos_pdf")
        politicas_pdf = request.files.get("politicas_pdf")

        if terminos_pdf and terminos_pdf.filename.endswith(".pdf"):
            filename = "terminos_condiciones.pdf"
            ruta_terminos = os.path.join(carpeta_config, filename)
            terminos_pdf.save(ruta_terminos)
            datos.terminos_pdf = filename

        if politicas_pdf and politicas_pdf.filename.endswith(".pdf"):
            filename = "politicas_privacidad.pdf"
            ruta_politicas = os.path.join(carpeta_config, filename)
            politicas_pdf.save(ruta_politicas)
            datos.politicas_pdf = filename

        if datos:
            datos.nombre = request.form["nombre"]
            datos.direccion = request.form["direccion"]
            datos.telefono = request.form["telefono"]
            datos.nit = request.form["nit"]
            datos.numero_cuenta = request.form["numero_cuenta"]
            datos.codigo_cuenta = request.form["codigo_cuenta"]

        else:
            datos = DatosConjunto(
                nombre=request.form["nombre"],
                direccion=request.form["direccion"],
                telefono=request.form["telefono"],
                nit=request.form["nit"],
                numero_cuenta=request.form["numero_cuenta"],
                codigo_cuenta=request.form["codigo_cuenta"],
                terminos_pdf="terminos_condiciones.pdf" if terminos_pdf else None,
                politicas_pdf="politicas_privacidad.pdf" if politicas_pdf else None
            )
            db.session.add(datos)

        db.session.commit()
        registrar_log(current_user.id,"Configuracion","Modifica Datos del conjunto") 
        flash("Datos del conjunto actualizados correctamente", "success")
        return redirect(url_for("config.gestionar_datos_conjunto"))
    return render_template("config/datos_conjunto.html", datos=datos)

@config_bp.route('/eliminar_pdf/<string:tipo>', methods=['POST','GET' ])
@login_required
@require_permission('Configuracion')
def eliminar_pdf(tipo):
    datos = DatosConjunto.query.first()
    base_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    carpeta_config = os.path.join(base_dir, 'static', 'configuracion')

    if tipo == 'terminos' and datos and datos.terminos_pdf:
        ruta = os.path.join(carpeta_config, datos.terminos_pdf)
        if os.path.exists(ruta):
            os.remove(ruta)
        datos.terminos_pdf = None

    elif tipo == 'politicas' and datos and datos.politicas_pdf:
        ruta = os.path.join(carpeta_config, datos.politicas_pdf)
        if os.path.exists(ruta):
            os.remove(ruta)
        datos.politicas_pdf = None

    db.session.commit()
    registrar_log(current_user.id, "Configuracion", f"Elimina archivo PDF: {tipo}")
    flash(f"Archivo de {tipo} eliminado correctamente.", "info")
    return redirect(url_for('config.gestionar_datos_conjunto'))

# Listar todos los roles
@config_bp.route('/roles', methods=['GET', 'POST'])
@login_required
@require_permission('Ver Roles')
def listar_roles():

    #roles = Roles.query.all()
    roles = Roles.query.filter(Roles.id != 99).all()
    permisos = Permisos.query.order_by(Permisos.tipo.asc()).all()
    registrar_log(current_user.id,"Roles","Lista Roles")
    
    return render_template('roles/gestionar_roles.html', roles=roles, permisos=permisos)


@config_bp.route('/roles/crear', methods=['GET', 'POST'])
@login_required
@require_permission('Crear Roles')
def gestionar_roles():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        permisos_seleccionados = request.form.getlist('permisos')

        if not nombre:
            flash("El nombre del rol es obligatorio.", "danger")
            return redirect(url_for('config.gestionar_roles'))

        nuevo_rol = Roles(nombre=nombre)
        permisos = Permisos.query.filter(Permisos.id.in_(permisos_seleccionados)).all()
        nuevo_rol.permisos.extend(permisos)

        db.session.add(nuevo_rol)
        db.session.commit()
        registrar_log(current_user.id,"Roles", "Crea rol id: "+ str(nuevo_rol.id)+" Nombre: "+str(nombre)) 
        flash("Rol creado correctamente.", "success")
        return redirect(url_for('config.gestionar_roles'))

    #roles = Roles.query.all()
    roles = Roles.query.filter(Roles.id != 99).all()

    permisos = Permisos.query.order_by(Permisos.tipo.asc()).all()
    return render_template('roles/crear_rol.html', roles=roles, permisos=permisos)

# Editar el rol que se desea
@config_bp.route('/roles/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@require_permission('Modificar Roles')
def editar_rol(id):
    rol = Roles.query.get_or_404(id)
    permisos = Permisos.query.all()  # Obtener todos los permisos disponibles

    if request.method == 'POST':
        nuevo_nombre = request.form.get('nombre')
        permisos_seleccionados = request.form.getlist('permisos')

        if not nuevo_nombre:
            flash('El nombre del rol no puede estar vacío', 'danger')
            return redirect(url_for('config.editar_rol', id=id))

        # Actualizar el nombre del rol
        rol.nombre = nuevo_nombre

        # Actualizar permisos asociados al rol
        rol.permisos.clear()
        for permiso_id in permisos_seleccionados:
            permiso = Permisos.query.get(permiso_id)
            if permiso:
                rol.permisos.append(permiso)

        db.session.commit()
        registrar_log(current_user.id,"Roles", "Edita rol id: "+ str(rol.id)+" Nombre: "+str(rol.nombre)) 
        flash('Rol actualizado correctamente', 'success')
        return redirect(url_for('config.listar_roles'))

    return render_template('roles/editar_rol.html', rol=rol, permisos=permisos)
# Elimina el rol seleccionado
@config_bp.route('/roles/eliminar_rol/<int:rol_id>', methods=['POST'])
@login_required
@require_permission('Eliminar Roles')
def eliminar_rol(rol_id):
    if request.method == 'POST':
        rol = Roles.query.get_or_404(rol_id)
        registrar_log(current_user.id,"Roles", "Elimina rol id: "+ str(rol.id)+" Nombre: "+str(rol.nombre)) 
        db.session.delete(rol)
        db.session.commit() 
        flash('Rol eliminado correctamente.', 'success')
        return redirect(url_for('config.gestionar_roles'))


# Listar todas las casas
@config_bp.route('/casas', methods=['GET'])
@login_required
@require_permission('Listar Unidades Residencial')
def listar_casas():
    casas = Casas.query.all()
    registrar_log(current_user.id,"Unidad Residencial", "Lista todas las torres-apartamentos") 
    return render_template('casas/listar_casas.html', casas=casas)

@config_bp.route('/torres/nueva', methods=['GET', 'POST'])
@login_required
@require_permission('Crear Torres')
def nueva_torre():
    if request.method == 'POST':
        nombre_torre = request.form.get('nombre')

        if not nombre_torre:
            flash('El nombre de la torre es obligatorio', 'danger')
            return redirect(url_for('config.nueva_torre'))

        # Verificar si la torre ya existe
        torre_existente = Torre.query.filter_by(nombre=nombre_torre).first()
        if torre_existente:
            flash('Esta torre ya existe', 'warning')
            return redirect(url_for('config.nueva_torre'))

        # Crear la nueva torre
        nueva_torre = Torre(nombre=nombre_torre)
        db.session.add(nueva_torre)
        db.session.commit()
        registrar_log(current_user.id,"Unidad Residencial", "Crea nueva torre id: "+ str(nueva_torre.id) + " nombre: "+str(nombre_torre)) 
        flash('Torre agregada correctamente', 'success')
        return redirect(url_for('config.nueva_casa'))
    torre = Torre.query.all()
    return render_template('casas/nueva_torre.html', torre=torre)

@config_bp.route('/torres/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@require_permission('Editar Torres')
def editar_torre(id):
    torre = Torre.query.get_or_404(id)

    if request.method == 'POST':
        nuevo_nombre = request.form.get('nombre')

        if not nuevo_nombre:
            flash('El nombre de la torre es obligatorio', 'danger')
            return redirect(url_for('config.editar_torre', id=id))

        torre.nombre = nuevo_nombre
        db.session.commit()
        registrar_log(current_user.id,"Unidad Residencial", "edita torre "+ str(torre.nombre)) 
        flash('Torre actualizada correctamente', 'success')
        return redirect(url_for('config.nueva_torre'))

    return render_template('casas/editar_torre.html', torre=torre)

@config_bp.route('/torres/eliminar/<int:id>', methods=['POST'])
@login_required
@require_permission('Eliminar Torres')
def eliminar_torre(id):
    torre = Torre.query.get_or_404(id)
    registrar_log(current_user.id,"Unidad Residencial", "Elimina torre id: "+ str(torre.id) + " nombre: "+str(torre.nombre)) 
    db.session.delete(torre)
    db.session.commit()
    
    flash('Torre eliminada correctamente', 'success')
    return redirect(url_for('config.nueva_torre'))

@config_bp.route('/apartamentos/nuevo', methods=['GET', 'POST'])
@login_required
@require_permission('Crear Apartamentos')
def nuevo_apartamento():
    if request.method == 'POST':
        numero_apartamento = request.form.get('numero')

        if not numero_apartamento:
            flash('El número del apartamento es obligatorio', 'danger')
            return redirect(url_for('config.nuevo_apartamento'))

        # Verificar si el apartamento ya existe
        apartamento_existente = Apartamento.query.filter_by(numero=numero_apartamento).first()
        if apartamento_existente:
            flash('Este apartamento ya existe', 'warning')
            return redirect(url_for('config.nuevo_apartamento'))

        # Crear el nuevo apartamento
        nuevo_apartamento = Apartamento(numero=numero_apartamento)
        db.session.add(nuevo_apartamento)
        db.session.commit()
        registrar_log(current_user.id,"Unidad Residencial", "Crea Nuevo apartamento id"+ str(nuevo_apartamento.id) + " numero: "+str(nuevo_apartamento))
        flash('Apartamento agregado correctamente', 'success')
        return redirect(url_for('config.nueva_casa'))
    
    
    apartamentos = Apartamento.query.all()
    return render_template('casas/nuevo_apartamento.html', apartamentos=apartamentos)

@config_bp.route('/apartamentos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@require_permission('Editar Apartamento')
def editar_apartamento(id):
    apartamento = Apartamento.query.get_or_404(id)

    if request.method == 'POST':
        nuevo_numero = request.form.get('numero')

        if not nuevo_numero:
            flash('El número del apartamento es obligatorio', 'danger')
            return redirect(url_for('config.editar_apartamento', id=id))

        apartamento.numero = nuevo_numero
        db.session.commit()
        registrar_log(current_user.id,"Unidad Residencial","Crea edita apartamento id"+ str(apartamento.id) + " numero: "+str(apartamento.numero))
        flash('Apartamento actualizado correctamente', 'success')
        return redirect(url_for('config.nuevo_apartamento'))

    return render_template('casas/editar_apartamento.html', apartamento=apartamento)

@config_bp.route('/apartamentos/eliminar/<int:id>', methods=['POST'])
@login_required
@require_permission('Eliminar Apartamento')
def eliminar_apartamento(id):
    apartamento = Apartamento.query.get_or_404(id)
    registrar_log(current_user.id,"Unidad Residencial", "Crea Nuevo apartamento id"+ str(apartamento.id) + " numero: "+str(apartamento.numero))
    db.session.delete(apartamento)
    db.session.commit()
    flash('Apartamento eliminado correctamente', 'success')
    return redirect(url_for('config.listar_apartamentos'))

# Crear nueva casa
@config_bp.route('/casas/nueva', methods=['GET', 'POST'])
@login_required
@require_permission('Crear Torre- Apartamento')
def nueva_casa():
    if request.method == 'POST':
        torre_nombre = request.form.get('torre')
        apartamento_numero = request.form.get('apartamento')



        # Crear la casa con los IDs de la torre y apartamento
        nueva_casa = Casas(id_torre=torre_nombre, id_apartamento=apartamento_numero)
        db.session.add(nueva_casa)
        db.session.commit()
        registrar_log(current_user.id,"Unidad Residencial", "Crea Nuevo torre con aparamento id"+ str(torre_nombre) + " numero: "+str(apartamento_numero))
        flash('Casa agregada correctamente', 'success')
        return redirect(url_for('config.listar_casas'))

    torres = Torre.query.all()
    apartamentos = Apartamento.query.all()
    return render_template('casas/nueva_casa.html', torres=torres, apartamentos=apartamentos)

# Editar una casa
@config_bp.route('/casas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@require_permission('Crear Torre- Apartamento')
def editar_casa(id):
    casa = Casas.query.get_or_404(id)

    if request.method == 'POST':
        torre_nombre = request.form.get('torre')
        apartamento_numero = request.form.get('apartamento')

        if not torre_nombre or not apartamento_numero:
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('config.editar_casa', id=id))

        # Buscar o crear la nueva torre
        torre = Torre.query.filter_by(nombre=torre_nombre).first()
        if not torre:
            torre = Torre(nombre=torre_nombre)
            db.session.add(torre)
            db.session.flush()

        # Buscar o crear el nuevo apartamento
        apartamento = Apartamento.query.filter_by(numero=apartamento_numero).first()
        if not apartamento:
            apartamento = Apartamento(numero=apartamento_numero)
            db.session.add(apartamento)
            db.session.flush()

        # Actualizar la casa con los nuevos IDs
        casa.id_torre = torre.id
        casa.id_apartamento = apartamento.id
        
        db.session.commit()

        registrar_log(current_user.id,"Unidad Residencial", "Edita torre con aparamento torre: "+ str(torre_nombre) + " apartamento: "+str(apartamento_numero))
        flash('Casa actualizada correctamente', 'success')
        return redirect(url_for('config.listar_casas'))

    torres = Torre.query.all()
    apartamentos = Apartamento.query.all()
    return render_template('casas/editar_casa.html', casa=casa, torres=torres, apartamentos=apartamentos)

# Eliminar una casa
@config_bp.route('/casas/eliminar/<int:id>', methods=['POST'])
@login_required
@require_permission('Crear Torre- Apartamento')
def eliminar_casa(id):
    casa = Casas.query.get_or_404(id)

    registrar_log(current_user.id,"Unidad Residencial", "Elimina torre con aparamento torre: "+ str(casa.torre.nombre) + " aparamento: "+str(casa.apartamento.numero))
    db.session.delete(casa)
    db.session.commit()
    flash('Casa eliminada correctamente', 'success')
    return redirect(url_for('config.listar_casas'))

# Listar todas las descripciones de PQRS
@config_bp.route('/descripcion_pqrs', methods=['GET'])
@login_required
@require_permission('Ver Descripciones Pqrs')
def listar_descripciones():
    descripciones = descripcion_pqrs.query.all()
    registrar_log(current_user.id,"Descripciones", "Lista descripciones pqrs")
    return render_template('descripcion_pqrs/listar_descripciones.html', descripciones=descripciones)

# Crear una nueva descripción de PQRS
@config_bp.route('/descripcion_pqrs/nueva', methods=['GET', 'POST'])
@login_required
@require_permission('Crear Descripcion')
def nueva_descripcion():
    tipos_pqrs = tipo_pqrs.query.all()

    if request.method == 'POST':
        tipo = request.form.get('tipo')
        descripcion = request.form.get('descripcion')
        id_tipo = request.form.get('id_tipo')

        if not tipo or not descripcion or not id_tipo:
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('config.nueva_descripcion'))

        nueva_desc = descripcion_pqrs(tipo=tipo, descripcion=descripcion, id_tipo=id_tipo)
        db.session.add(nueva_desc)
        db.session.commit()
        registrar_log(current_user.id,"Descripciones", "Crea Nueva descripcion id "+ str(nueva_desc.id) + " tipo: "+ str(tipo) + " descripcion: "+str(descripcion)+ " tipo_pqrs: "+str(id_tipo))
        flash('Descripción de PQRS agregada correctamente', 'success')
        return redirect(url_for('config.listar_descripciones'))

    return render_template('descripcion_pqrs/nueva_descripcion.html', tipos_pqrs=tipos_pqrs)

# Editar una descripción de PQRS
@config_bp.route('/descripcion_pqrs/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@require_permission('Modificar Descripcion')
def editar_descripcion(id):
    descripcion_pqrs_ = descripcion_pqrs.query.get_or_404(id)
    tipos_pqrs = tipo_pqrs.query.all()

    if request.method == 'POST':
        descripcion_pqrs_.tipo = request.form.get('tipo')
        descripcion_pqrs_.descripcion = request.form.get('descripcion')
        descripcion_pqrs_.id_tipo = request.form.get('id_tipo')

        if not descripcion_pqrs_.tipo or not descripcion_pqrs_.descripcion or not descripcion_pqrs_.id_tipo:
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('config.editar_descripcion', id=id))

        db.session.commit()
        registrar_log(current_user.id,"Descripciones", "Edita descripcion id: "+ str(descripcion_pqrs_.id) )
        flash('Descripción de PQRS actualizada correctamente', 'success')
        return redirect(url_for('config.listar_descripciones'))

    return render_template('descripcion_pqrs/editar_descripcion.html', descripcion_pqrs=descripcion_pqrs_, tipos_pqrs=tipos_pqrs)

# Eliminar una descripción de PQRS
@config_bp.route('/descripcion_pqrs/eliminar/<int:id>', methods=['POST'])
@login_required
@require_permission('Eliminar Descripcion')
def eliminar_descripcion(id):
    descripcion_pqrs_ = descripcion_pqrs.query.get_or_404(id)

    registrar_log(current_user.id,"Descripciones", "Edita descripcion id: "+ str(descripcion_pqrs_.id))
    db.session.delete(descripcion_pqrs_)
    db.session.commit()
    flash('Descripción de PQRS eliminada correctamente', 'success')
    return redirect(url_for('config.listar_descripciones'))

# Listar espacios de reserva
@config_bp.route('/espacios')
@login_required
@require_permission('Ver Espacios')
def listar_espacios():
    espacios = Espacios_reserva.query.all()
    registrar_log(current_user.id,"Espacios_Reserva", "Lista espacios de reservas")
    return render_template('reservas/listar_espacios.html', espacios=espacios)

# Crear nuevo espacio de reserva
@config_bp.route('/admin/espacios/crear', methods=['GET', 'POST'])
@login_required
@require_permission('Crear Espacios')
def crear_espacio():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        capacidad = request.form.get('capacidad')

        if not nombre or not capacidad:
            flash("El nombre y la capacidad son obligatorios.", "danger")
            return redirect(url_for('config.crear_espacio'))

        nuevo_espacio = Espacios_reserva(nombre=nombre, descripcion=descripcion, valor=int(capacidad))
        db.session.add(nuevo_espacio)
        db.session.commit()
        registrar_log(current_user.id,"Espacios_Reserva", "Crea espacio id "+ str(nuevo_espacio.id) + " Nombre: "+ str(nombre) + " descripcion: "+str(descripcion)+ " Valor: "+str(capacidad))
        flash("Espacio creado correctamente.", "success")
        return redirect(url_for('config.listar_espacios'))

    return render_template('reservas/crear_espacio.html')

# Editar espacio de reserva
@config_bp.route('/admin/espacios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@require_permission('Modificar Espacios')
def editar_espacio(id):
    espacio = Espacios_reserva.query.get_or_404(id)

    if request.method == 'POST':
        espacio.nombre = request.form.get('nombre')
        espacio.descripcion = request.form.get('descripcion')
        espacio.capacidad = request.form.get('capacidad')
        estado = request.form.get('estado')  # Captura el estado desde el formulario
        espacio.estado = bool(int(estado))  # Convierte el estado a booleano

        db.session.commit()
        registrar_log(current_user.id,"Espacios_Reserva", "Edita espacio id "+ str(espacio.id) + " Nombre: "+ str(espacio.nombre) + " descripcion: "+str(espacio.descripcion)+ " Valor: "+str(espacio.capacidad)+ " Estado: "+str(espacio.estado) )
        flash("Espacio actualizado correctamente.", "success")
        return redirect(url_for('config.listar_espacios'))

    return render_template('reservas/editar_espacio.html', espacio=espacio)

# Eliminar espacio de reserva
@config_bp.route('/admin/espacios/eliminar/<int:id>', methods=['POST'])
@login_required
@require_permission('Eliminar Espacio')
def eliminar_espacio(id):
    espacio = Espacios_reserva.query.get_or_404(id)

    registrar_log(current_user.id,"Espacios_Reserva", "Elimina espacio id "+ str(espacio.id) + " Nombre: "+ str(espacio.nombre) + " descripcion: "+str(espacio.descripcion)+ " Valor: "+str(espacio.capacidad)+ " Estado: "+str(espacio.estado))
    db.session.delete(espacio)
    db.session.commit()
    flash("Espacio eliminado correctamente.", "success")
    return redirect(url_for('config.listar_espacios'))

