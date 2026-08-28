import logging
from firebase_admin import firestore

logger = logging.getLogger(__name__)

def get_firestore_client():
    try:
        return firestore.client()
    except Exception as e:
        logger.warning(f"No se pudo inicializar cliente de Firestore: {e}")
        return None


def sync_medicamento_usuario_firestore(med_user):
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc_id = f"{med_user.usuario_id}_{med_user.medicamento_id}"
        doc_ref = db.collection('medicamentos_usuario').document(doc_id)
        
        datos = {
            'id': med_user.id,
            'usuario_id': med_user.usuario_id,
            'usuario_username': med_user.usuario.username,
            'usuario_nombre': med_user.usuario.nombre_para_mostrar(),
            'medicamento_id': med_user.medicamento_id,
            'medicamento_nombre': med_user.medicamento.nombre_comercial,
            'medicamento_generico': med_user.medicamento.nombre_generico,
            'dosis': med_user.dosis or '',
            'cantidad_prescrita': med_user.cantidad_prescrita or '',
            'fuente_asignacion': med_user.fuente_asignacion,
            'activo': med_user.activo,
            'fecha_asignacion': med_user.fecha_asignacion.isoformat() if med_user.fecha_asignacion else None,
            'actualizado': firestore.SERVER_TIMESTAMP,
        }
        
        doc_ref.set(datos, merge=True)
        
        if med_user.usuario.firebase_uid:
            db.collection('usuarios').document(med_user.usuario.firebase_uid)\
              .collection('medicamentos_asignados').document(str(med_user.medicamento_id))\
              .set(datos, merge=True)
        
        if med_user.firestore_id != doc_id:
            med_user.firestore_id = doc_id
            med_user.save(update_fields=['firestore_id'])

        return doc_ref
    except Exception as e:
        logger.error(f"Error sincronizando MedicamentoUsuario a Firestore: {e}")
        return None


def eliminar_medicamento_usuario_firestore(usuario_id, medicamento_id, firebase_uid=None):
    db = get_firestore_client()
    if not db:
        return

    try:
        doc_id = f"{usuario_id}_{medicamento_id}"
        db.collection('medicamentos_usuario').document(doc_id).delete()
        if firebase_uid:
            db.collection('usuarios').document(firebase_uid)\
              .collection('medicamentos_asignados').document(str(medicamento_id)).delete()
    except Exception as e:
        logger.error(f"Error eliminando MedicamentoUsuario en Firestore: {e}")


def sync_derecho_peticion_firestore(peticion):
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc_ref = db.collection('derechos_peticion').document(peticion.numero_radicado)
        
        datos = {
            'id': peticion.id,
            'numero_radicado': peticion.numero_radicado,
            'usuario_id': peticion.usuario_id,
            'usuario_username': peticion.usuario.username,
            'usuario_nombre': peticion.usuario.nombre_para_mostrar(),
            'usuario_cedula': peticion.usuario.cedula or '',
            'usuario_email': peticion.usuario.email or '',
            'usuario_telefono': peticion.usuario.telefono or '',
            'medicamento_id': peticion.medicamento_id,
            'medicamento_nombre': peticion.medicamento.nombre_comercial,
            'medicamento_generico': peticion.medicamento.nombre_generico,
            'sede_id': peticion.sede_id if peticion.sede else None,
            'sede_nombre': peticion.sede.nombre if peticion.sede else '',
            'estado': peticion.estado,
            'fecha_radicacion': peticion.fecha_radicacion.isoformat() if peticion.fecha_radicacion else None,
            'fecha_respuesta': peticion.fecha_respuesta.isoformat() if peticion.fecha_respuesta else None,
            'observaciones_eps': peticion.observaciones_eps or '',
            'atendido_por_id': peticion.atendido_por_id if peticion.atendido_por else None,
            'atendido_por_nombre': peticion.atendido_por.nombre_para_mostrar() if peticion.atendido_por else '',
            'actualizado': firestore.SERVER_TIMESTAMP,
        }
        
        doc_ref.set(datos, merge=True)
        
        if peticion.firestore_id != peticion.numero_radicado:
            peticion.firestore_id = peticion.numero_radicado
            peticion.save(update_fields=['firestore_id'])

        return doc_ref
    except Exception as e:
        logger.error(f"Error sincronizando DerechoPeticion a Firestore: {e}")
        return None
