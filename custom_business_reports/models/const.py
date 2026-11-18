# -*- coding: utf-8 -*-
"""Constantes compartidas por los modelos del módulo.

Se concentran aquí para no repetir listas de valores en varios archivos y
para que un cambio (por ejemplo, el nombre del campo Studio) se haga en un
solo lugar.
"""

# Campo creado con Studio en crm.lead que guarda la "Calidad del lead".
# Valores actuales en DACSA: Idóneo, Bueno, Inadecuado, Recompra.
# El módulo lo lee de forma dinámica: si no existe, el segmento no se calcula
# pero el resto del módulo funciona.
QUALITY_FIELD = 'x_studio_calidad_del_lead'

# Segmento comercial que usan los reportes de Mauricio.
SEGMENT_SELECTION = [
    ('sin_recompra', 'Sin recompra'),
    ('recompra', 'Recompra'),
    ('inadecuado', 'Inadecuado'),
]

# Grupo al que pertenece cada etapa del CRM para fines de reporte.
# - prospeccion: trabajo previo a la invitación (Idea ... Contactar más tarde)
# - por_enviar:  hay invitación y se está cotizando (Invitación ... En revisión)
# - cotizado:    la cotización ya salió (Enviada, En Pausa, Ganado, Cancelado
#                y los perdidos, que Odoo archiva con razón de pérdida)
# - declinado:   DACSA decidió no participar (No se participó)
# - excluido:    no debe aparecer en tableros (Ganados en 0's)
STAGE_GROUP_SELECTION = [
    ('prospeccion', 'Prospección'),
    ('por_enviar', 'Por enviar (cotizando)'),
    ('cotizado', 'Cotizado'),
    ('declinado', 'Declinado'),
    ('excluido', 'Excluido de tableros'),
]

# Grupos de etapa en los que la oportunidad sigue "viva" y por lo tanto
# tiene sentido medir días sin movimiento.
OPEN_STAGE_GROUPS = ('prospeccion', 'por_enviar', 'cotizado')

# Semáforo de seguimiento (días sin movimiento).
IDLE_WARNING_DAYS = 30   # a partir de aquí: ámbar
IDLE_LATE_DAYS = 90      # a partir de aquí: rojo

# Campos que escribe el sistema y que NO cuentan como "movimiento" del lead.
NO_MOVE_FIELDS = {
    'automated_probability',
    'report_last_move_date',
    'report_segment',
    'report_invitation_status',
    'report_close_status',
    'message_main_attachment_id',
}

# ----------------------------------------------------------------------
# Etapa 2 · Tablero comercial
# ----------------------------------------------------------------------

# Estatus "abierto" de la etapa, para los listados del pipeline.
# - enviada: la cotización se envió y se espera respuesta del cliente
# - pausa:   el cliente pospuso el proyecto (En Pausa)
OPEN_STATUS_SELECTION = [
    ('enviada', 'Enviada · pendiente de respuesta'),
    ('pausa', 'En pausa'),
]

# Clasificación de una invitación a cotizar (gráfica "Invitaciones a cotizar"):
# atendida (cotizada) por segmento, o no atendida (se declinó).
INVITATION_STATUS_SELECTION = [
    ('atendido_sin_recompra', 'Atendido · Sin recompra'),
    ('atendido_recompra', 'Atendido · Recompra'),
    ('atendido_inadecuado', 'Atendido · Inadecuado'),
    ('atendido_sin_segmento', 'Atendido · Sin segmento'),
    ('no_atendido', 'No atendido (no se participó)'),
]

# Resultado de una cotización cerrada (gráfica "Ganados y perdidos"):
# ganada o perdida, por segmento.
CLOSE_STATUS_SELECTION = [
    ('ganado_sin_recompra', 'Ganado · Sin recompra'),
    ('ganado_recompra', 'Ganado · Recompra'),
    ('ganado_otro', 'Ganado · Otro segmento'),
    ('perdido_sin_recompra', 'Perdido · Sin recompra'),
    ('perdido_recompra', 'Perdido · Recompra'),
    ('perdido_otro', 'Perdido · Otro segmento'),
]
