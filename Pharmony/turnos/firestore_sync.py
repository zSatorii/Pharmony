from firebase_admin import firestore

db = firestore.client()

def sync_turno_a_firestore(turno):
    doc_ref = db.collection('turnos').document(turno.codigo_ticket)
    doc_ref.set({
        'codigo_ticket': turno.codigo_ticket,
        'usuario_id': turno.usuario.id,
        'usuario_username': turno.usuario.username,
        'sede_id': turno.sede.id,
        'sede_nombre': turno.sede.nombre,
        'medicamento_id': turno.medicamento.id,
        'medicamento_nombre': turno.medicamento.nombre_comercial,
        'estado': turno.estado,
        'motivo_estado': turno.motivo_estado or '',
        'posicion_cola': turno.posicion_cola,
        'auxiliar_asignado_id': turno.auxiliar_asignado.id if turno.auxiliar_asignado else None,
        'auxiliar_username': turno.auxiliar_asignado.username if turno.auxiliar_asignado else None,
        'auxiliar_nombre': turno.auxiliar_asignado.nombre_para_mostrar() if turno.auxiliar_asignado else None,
        'direccion_envio': turno.direccion_envio,
        'fecha_solicitud': turno.fecha_solicitud.isoformat() if turno.fecha_solicitud else None,
        'fecha_finalizacion': turno.fecha_finalizacion.isoformat() if turno.fecha_finalizacion else None,
    })
    turno.firestore_id = turno.codigo_ticket
    turno.save(update_fields=['firestore_id'])
    return doc_ref


def sync_mensaje_a_firestore(turno, remitente, contenido, archivo_url=None):
    nombre_mostrar = f"{remitente.first_name} {remitente.last_name}".strip() or remitente.username
    db.collection('turnos').document(turno.codigo_ticket).collection('mensajes').add({
        'remitente_id': remitente.id,
        'remitente_username': remitente.username,
        'remitente_nombre': nombre_mostrar,
        'contenido': contenido,
        'archivo_url': archivo_url,
        'fecha': firestore.SERVER_TIMESTAMP,
    })

def sync_auxiliar_sede_a_firestore(auxiliar_sede):
    db.collection('auxiliares_sede').document(f"{auxiliar_sede.usuario_id}_{auxiliar_sede.sede_id}").set({
        'usuario_id': auxiliar_sede.usuario_id,
        'usuario_username': auxiliar_sede.usuario.username,
        'sede_id': auxiliar_sede.sede_id,
        'sede_nombre': auxiliar_sede.sede.nombre,
        'activo': auxiliar_sede.activo,
    })


def eliminar_auxiliar_sede_de_firestore(usuario_id, sede_id):
    db.collection('auxiliares_sede').document(f"{usuario_id}_{sede_id}").delete()