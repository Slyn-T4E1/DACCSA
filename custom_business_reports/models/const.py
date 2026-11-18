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
    'message_main_attachment_id',
}
