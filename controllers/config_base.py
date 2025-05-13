from flask_login import current_user
from models.roles import RolPermiso, Permisos
from app import db

def obtener_permisos_usuario():
    """
    Retorna una lista de nombres de permisos que tiene el usuario actual usando la tabla rol_permiso.
    """
    if not current_user.is_authenticated:
        return []

    permisos = (
        db.session.query(Permisos.nombre)
        .join(RolPermiso, Permisos.id == RolPermiso.permiso_id)
        .filter(RolPermiso.rol_id == current_user.id_rol)
        .all()
    )

    return [permiso.nombre for permiso in permisos]
