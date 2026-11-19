# -*- coding: utf-8 -*-
"""Configuración inicial al instalar el módulo (solo corre en la instalación).

1. Asigna el grupo de reporte a las etapas existentes, reconociéndolas por
   su nombre en cualquiera de los idiomas instalados.
2. Crea las reglas de segmento a partir de las opciones de "Calidad del lead".
3. Calcula el segmento de todas las oportunidades.
4. Llena "Último movimiento" con la mejor fecha disponible del historial.
5. Pone fecha de cierre a las oportunidades que ya estaban en "Cancelado".

Todo es seguro de repetir: solo llena lo que está vacío.
"""
import logging
import unicodedata

from odoo.tools import SQL

from .models.const import QUALITY_FIELD

_logger = logging.getLogger(__name__)

# Nombre de etapa (normalizado) -> (grupo de reporte, registrar fecha de cierre)
DEFAULT_STAGE_GROUPS = {
    'idea': ('prospeccion', False),
    'se toco puerta': ('prospeccion', False),
    'en comunicacion actualmente': ('prospeccion', False),
    'en comunicacion': ('prospeccion', False),
    'contactar mas tarde': ('prospeccion', False),
    'invitacion a cotizar': ('por_enviar', False),
    'en cotizacion': ('por_enviar', False),
    'en revision': ('por_enviar', False),
    'enviada': ('cotizado', False),
    'en pausa': ('cotizado', False),
    'ganado': ('cotizado', False),
    'cancelado': ('cotizado', True),
    'no se participo': ('declinado', False),
    "ganados en 0's": ('excluido', False),
    'ganados en ceros': ('excluido', False),
}

# Etapa 2: nombre de etapa (normalizado) -> listado del pipeline
DEFAULT_OPEN_STATUS = {
    'enviada': 'enviada',
    'en pausa': 'pausa',
}

# Etapa 3: palabra en el nombre de la posición (normalizado) -> tipo de partida.
# El orden importa: "anticipo" e "inventario" se revisan antes que el resto.
DEFAULT_PARTIDAS = [
    ('anticipo', 'otro'),
    ('inventario', 'otro'),
    ('material', 'materiales'),
    ('mano de obra', 'mano_obra'),
    ('subcontrat', 'subcontratistas'),
    ('equipo', 'equipo_herramienta'),
    ('herramienta', 'equipo_herramienta'),
    ('indirecto', 'indirectos'),
    ('venta', 'ventas'),
    ('ingreso', 'ventas'),
    ('igreso', 'ventas'),
    ('estimacion', 'ventas'),
]

# Abreviaturas usadas en DACSA como primera palabra del nombre (MO PA, MAT ISO, Herr)
DEFAULT_PARTIDA_PREFIXES = {
    'mo': 'mano_obra',
    'mat': 'materiales',
    'herr': 'equipo_herramienta',
}

# Palabra en la etiqueta de la calidad (normalizada) -> segmento
DEFAULT_SEGMENTS = {
    'idoneo': 'sin_recompra',
    'bueno': 'sin_recompra',
    'inadecuado': 'inadecuado',
    'recompra': 'recompra',
}


def _normalize(text):
    """Minúsculas, sin acentos y con apóstrofo simple, para comparar nombres."""
    text = (text or '').replace('’', "'").strip().lower()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def _setup_stage_groups(env):
    """Paso 1: grupo de reporte por etapa (solo etapas sin configurar)."""
    langs = [code for code, _name in env['res.lang'].get_installed()]
    for stage in env['crm.stage'].search([('report_stage_group', '=', False)]):
        names = {_normalize(stage.with_context(lang=lang).name) for lang in langs}
        match = next((DEFAULT_STAGE_GROUPS[n] for n in names if n in DEFAULT_STAGE_GROUPS), None)
        if match:
            stage.write({'report_stage_group': match[0], 'report_close_on_enter': match[1]})
            _logger.info('Etapa "%s": grupo de reporte %s', stage.name, match[0])
        else:
            _logger.info('Etapa "%s" sin grupo de reporte: configurar a mano', stage.name)


def _setup_open_status(env):
    """Etapa 2: marca las etapas "Enviada" y "En Pausa" para sus listados.

    Se llama al instalar y desde la migración 19.0.2.0.0 (bases que ya tenían
    la Etapa 1). Solo llena etapas sin configurar.
    """
    langs = [code for code, _name in env['res.lang'].get_installed()]
    for stage in env['crm.stage'].search([('report_open_status', '=', False)]):
        names = {_normalize(stage.with_context(lang=lang).name) for lang in langs}
        status = next((DEFAULT_OPEN_STATUS[n] for n in names if n in DEFAULT_OPEN_STATUS), None)
        if status:
            stage.report_open_status = status
            _logger.info('Etapa "%s": listado del pipeline %s', stage.name, status)


def _setup_partidas(env):
    """Etapa 3: tipo de partida de las posiciones presupuestarias por su nombre.

    Se llama al instalar y desde la migración 19.0.3.0.0. Solo llena
    posiciones sin tipo; las que no se reconocen se configuran a mano en
    Proyecto › Configuración › Partidas de posiciones presupuestarias.
    """
    posts = env['account.budget.post'].search([('report_partida', '=', False)])
    assigned = 0
    for post in posts:
        name = _normalize(post.name)
        partida = next((value for word, value in DEFAULT_PARTIDAS if word in name), None)
        if not partida and name:
            partida = DEFAULT_PARTIDA_PREFIXES.get(name.split()[0])
        if partida:
            post.report_partida = partida
            assigned += 1
    _logger.info('Tipo de partida asignado a %s de %s posiciones presupuestarias', assigned, len(posts))


def _setup_segment_rules(env):
    """Paso 2: reglas de segmento desde las opciones de "Calidad del lead"."""
    Rule = env['crm.lead.segment.rule']
    if QUALITY_FIELD not in env['crm.lead']._fields:
        _logger.warning('No existe el campo %s: no se crean reglas de segmento', QUALITY_FIELD)
        return
    if Rule.search_count([]):
        return
    vals_list = []
    for sequence, (value, label) in enumerate(Rule._selection_quality_value(), start=1):
        text = _normalize(f'{value} {label}')
        segment = next((seg for word, seg in DEFAULT_SEGMENTS.items() if word in text), None)
        if segment:
            vals_list.append({'sequence': sequence * 10, 'quality_value': value, 'segment': segment})
    if vals_list:
        # Al crear las reglas se recalcula el segmento de todas las oportunidades.
        Rule.create(vals_list)


def _fill_last_move_date(env):
    """Paso 4: último movimiento inicial.

    No se usa write_date porque la migración a v19 tocó todas las
    oportunidades. Se toma la fecha más reciente entre: creación, último cambio
    de etapa, fecha de cierre, último mensaje/nota de una persona en el chatter
    y última actividad programada.
    """
    env.cr.execute(SQL("""
        UPDATE crm_lead l
           SET report_last_move_date = GREATEST(
                   l.create_date, l.date_last_stage_update, l.date_closed,
                   msg.last_date, act.last_date)
          FROM crm_lead l2
          LEFT JOIN (
                SELECT m.res_id, MAX(m.date) AS last_date
                  FROM mail_message m
                 WHERE m.model = 'crm.lead'
                   AND m.message_type <> 'user_notification'
                   AND (m.author_id IS NULL OR m.author_id <> %(odoobot)s)
              GROUP BY m.res_id
          ) msg ON msg.res_id = l2.id
          LEFT JOIN (
                SELECT a.res_id, MAX(a.create_date) AS last_date
                  FROM mail_activity a
                 WHERE a.res_model = 'crm.lead'
              GROUP BY a.res_id
          ) act ON act.res_id = l2.id
         WHERE l.id = l2.id
           AND l.report_last_move_date IS NULL
    """, odoobot=env.ref('base.partner_root').id))
    _logger.info('Último movimiento inicial calculado en %s oportunidades', env.cr.rowcount)


def _fill_cancel_close_date(env):
    """Paso 5: fecha de cierre de oportunidades que ya estaban en "Cancelado".

    Odoo no la registraba. Se usa la fecha en que entraron a la etapa
    (último cambio de etapa) como mejor aproximación. Se puede corregir a mano.
    """
    stages = env['crm.stage'].search([('report_close_on_enter', '=', True)])
    if not stages:
        return
    env.cr.execute(SQL("""
        UPDATE crm_lead
           SET date_closed = COALESCE(date_last_stage_update, write_date)
         WHERE stage_id IN %s AND date_closed IS NULL
    """, tuple(stages.ids)))
    _logger.info('Fecha de cierre inicial en %s oportunidades canceladas', env.cr.rowcount)


def post_init_hook(env):
    _setup_stage_groups(env)
    _setup_open_status(env)
    _setup_partidas(env)
    _setup_segment_rules(env)
    # Paso 3: por si las reglas ya existían, recalcular segmentos.
    env['crm.lead.segment.rule']._recompute_all_leads()
    _fill_last_move_date(env)
    _fill_cancel_close_date(env)
