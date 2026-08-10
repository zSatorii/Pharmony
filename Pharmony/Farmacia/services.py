from django.db import transaction
from firebase_admin import auth as firebase_auth, firestore


class CrearUsuarioEpsError(Exception):
    """Error controlado al crear un usuario EPS (Django/Firebase/Firestore)."""
    pass


def crear_usuario_eps(usuario, password_plano=None):
    """
    Sincroniza un usuario recién creado en Django con Firebase Auth y Firestore.

    Se asume que 'usuario' ya fue guardado en la base de datos de Django
    (por ejemplo, con Usuario.objects.create_user(...) o desde un formulario
    del admin/API que ya llamó a obj.save()).
    """
    if usuario.firebase_uid:
        # Ya estaba sincronizado antes (ej. una edición), no se vuelve a crear.
        return {"firebase_ok": True, "mensaje": "Usuario ya estaba sincronizado con Firebase."}

    if not password_plano:
        return {
            "firebase_ok": False,
            "mensaje": (
                f"Usuario {usuario.email} creado solo en Django: no se pudo crear en "
                f"Firebase porque no se recibió la contraseña en texto plano."
            ),
        }

    try:
        fb_user = firebase_auth.create_user(
            email=usuario.email,
            password=password_plano,
            display_name=f"{usuario.first_name} {usuario.last_name}".strip() or usuario.username,
        )
        usuario.firebase_uid = fb_user.uid
        usuario.save(update_fields=["firebase_uid"])

        db = firestore.client()
        db.collection("usuarios").document(fb_user.uid).set(
            {
                "nombre": usuario.first_name,
                "apellido": usuario.last_name,
                "email": usuario.email,
                "telefono": usuario.telefono or "",
                "rol": usuario.rol,
                "eps_id": usuario.eps.id if usuario.eps else None,
                "face_registered": False,
            },
            merge=True,
        )
        return {"firebase_ok": True, "mensaje": f"Usuario {usuario.email} sincronizado correctamente."}

    except Exception as e:
        return {
            "firebase_ok": False,
            "mensaje": f"Usuario {usuario.email} creado en Django, pero falló la sincronización con Firebase: {e}",
        }


def crear_usuario_eps_completo(datos, password_plano):
    """
    Crea un usuario de cero: Django + Firebase + Firestore, en una sola
    transacción. Pensado para usarse desde el futuro endpoint de 'api/',
    donde no hay un ModelForm del admin de por medio.

    Si Firebase falla, se revierte la creación en Django (a diferencia del
    admin, que hoy deja el usuario "a medias" y solo avisa con un mensaje).
    """
    from django.contrib.auth import get_user_model

    Usuario = get_user_model()

    with transaction.atomic():
        usuario = Usuario.objects.create_user(password=password_plano, **datos)

        resultado = crear_usuario_eps(usuario, password_plano=password_plano)

        if not resultado["firebase_ok"]:
            # Revertimos: no queremos usuarios "fantasma" solo en Django
            # cuando la creación se hizo desde la API (a diferencia del
            # admin, donde un staff puede decidir dejarlo así y arreglarlo
            # manualmente después).
            raise CrearUsuarioEpsError(resultado["mensaje"])

        return usuario