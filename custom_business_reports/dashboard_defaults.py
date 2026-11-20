# -*- coding: utf-8 -*-
"""Tableros de fábrica de la app "Tableros DACSA" (Etapa 6).

Se crean al instalar y en la migración 19.0.6.0.0, solo si no existen (se
reconocen por su identificador externo). Después el usuario los puede
cambiar desde la app sin que una actualización del módulo los sobrescriba.

Los elementos con 'since' se agregaron después (19.0.8.0.0): la migración de
esa versión los agrega a los tableros que ya existen, solo si no hay un
elemento con el mismo título. Su 'sequence' fija el lugar en el tablero.

Cada tablero se describe con diccionarios:
  filtros:   etiqueta, tipo, campo por omisión, modelo de los registros...
  elementos: tipo, modelo, dominio, agrupación, medidas y cómo se aplican
             los filtros ("map": {filtro: campo o None para no aplicarlo}).
"""
import logging

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Piezas de dominio del CRM (iguales a las de las etapas 1 y 2)
# ---------------------------------------------------------------------------
OPP = "('type', '=', 'opportunity')"
ARCHIVED = "('active', 'in', [True, False])"
NOT_EXCLUDED = "('report_stage_group', '!=', 'excluido')"
INVITATIONS = "('report_invitation_status', '!=', False)"
ATTENDED = "('report_invitation_status', 'in', ['atendido_sin_recompra', 'atendido_recompra', " \
           "'atendido_inadecuado', 'atendido_sin_segmento'])"
WON = "('report_close_status', 'in', ['ganado_sin_recompra', 'ganado_recompra', 'ganado_otro'])"
LOST = "('report_close_status', 'in', ['perdido_sin_recompra', 'perdido_recompra', 'perdido_otro'])"
SENT_PENDING = "('report_open_status', '=', 'enviada')", "('won_status', '=', 'pending')"
GOAL = 'business.sales.goal'


def d(*parts):
    return '[%s]' % ', '.join(parts)


def m(name, code, aggregate='count', field=None, **kw):
    """Medida."""
    return dict(name=name, code=code, aggregate=aggregate, field=field, **kw)


COMMERCIAL = {
    'xmlid': 'dashboard_commercial',
    'name': 'Seguimiento comercial',
    'category': 'Comercial',
    'sequence': 10,
    'groups': ['sales_team.group_sale_salesman'],
    'description': 'Dirección de Nuevos Proyectos: invitaciones, cotizaciones cerradas, venta y embudo por '
                   'segmento. Excluye "Ganados en 0\'s".',
    'filters': [
        dict(key='periodo', name='Periodo', filter_type='date', field_name='create_date', default_period='this_year'),
        dict(key='vendedor', name='Vendedor', filter_type='many2one', field_name='user_id', comodel='res.users',
             multiple=True, record_domain="[('share', '=', False)]"),
        dict(key='segmento', name='Segmento', filter_type='selection', field_name='report_segment',
             selection_model='crm.lead'),
    ],
    'widgets': [
        # ---------------- Indicadores ----------------
        dict(type='kpi', name='Venta ganada', code='venta', width='3', model='crm.lead',
             domain=d(OPP, "('won_status', '=', 'won')", NOT_EXCLUDED), map={'periodo': 'date_closed'},
             measures=[m('Venta', 'venta', 'sum', 'expected_revenue')], value_format='monetary',
             subtitle='por fecha de cierre', color='#EFF6FF'),
        dict(type='kpi', name='Ganados', code='ganados', width='3', model='crm.lead', domain=d(OPP, ARCHIVED, WON),
             map={'periodo': 'date_closed'}, measures=[m('Ganados', 'ganados')], value_format='integer',
             abbreviate=False, subtitle='cotizaciones ganadas', color='#EFF6FF'),
        dict(type='kpi', name='Perdidos', code='perdidos', width='3', model='crm.lead', domain=d(OPP, ARCHIVED, LOST),
             map={'periodo': 'date_closed'}, measures=[m('Perdidos', 'perdidos')], value_format='integer',
             abbreviate=False, subtitle='cotizaciones perdidas', color='#FEF2F2'),
        dict(type='kpi', name='Efectividad de cierre', code='efectividad', width='3',
             formula='div(ganados, ganados + perdidos)', value_format='percent',
             subtitle='ganados / (ganados + perdidos)', color='#F0FDF4'),
        dict(type='kpi', name='Invitaciones a cotizar', code='invitaciones', width='3', model='crm.lead',
             domain=d(OPP, ARCHIVED, INVITATIONS), measures=[m('Invitaciones', 'invitaciones')],
             value_format='integer', abbreviate=False, subtitle='cotizadas + declinadas', color='#F9FAFB'),
        dict(type='kpi', name='Atendidas (cotizadas)', code='atendidas', width='3', model='crm.lead',
             domain=d(OPP, ARCHIVED, ATTENDED), measures=[m('Atendidas', 'atendidas')],
             value_format='integer', abbreviate=False, subtitle='por fecha de creación', color='#F9FAFB'),
        dict(type='kpi', name='% de bateo', code='bateo', width='3', formula='div(ganados, atendidas)',
             value_format='percent', subtitle='ganados / atendidas', color='#F0FDF4'),
        dict(type='kpi', name='Pipeline enviado', code='pipeline', width='3', model='crm.lead',
             domain=d(OPP, "('report_open_status', '=', 'enviada')", "('won_status', '=', 'pending')"),
             map={'periodo': None}, measures=[m('Pipeline', 'pipeline', 'sum', 'expected_revenue')],
             value_format='monetary', subtitle='pendiente de respuesta, hoy', color='#FFF7ED'),
        # 19.0.8.0.0: meta de venta configurable (CRM › Configuración › Metas de venta mensuales)
        dict(type='kpi', name='Meta de venta', code='meta', width='6', model=GOAL, since='19.0.8.0.0', sequence=81,
             map={'periodo': 'date'}, measures=[m('Meta', 'meta', 'sum', 'amount')], value_format='monetary',
             subtitle='Σ metas mensuales del periodo (de la empresa)', color='#EFF6FF'),
        dict(type='kpi', name='Avance vs meta', code='avance_meta', width='6', since='19.0.8.0.0', sequence=82,
             formula='div(venta, meta)', value_format='percent', color_mode='threshold', threshold='1',
             subtitle='venta ganada / meta; rojo si es menor al 100 %', color='#F0FDF4'),
        # ---------------- Gráficas ----------------
        dict(type='section', name='Invitaciones a cotizar'),
        dict(type='chart', name='Invitaciones a cotizar por mes', width='6', model='crm.lead',
             domain=d(OPP, ARCHIVED, INVITATIONS), groupby='create_date', interval='month',
             groupby2='report_invitation_status', chart_type='bar_stacked',
             measures=[m('Invitaciones', 'invitaciones')]),
        dict(type='chart', name='Histórico de invitaciones por trimestre', width='6', model='crm.lead',
             domain=d(OPP, ARCHIVED, INVITATIONS), groupby='create_date', interval='quarter',
             groupby2='report_invitation_status', chart_type='bar_stacked', map={'periodo': None},
             subtitle='todos los años', measures=[m('Invitaciones', 'invitaciones')]),
        # 19.0.8.0.0: la tabla "mes a mes" del requerimiento, con los meses en columnas
        dict(type='table', name='Invitaciones a cotizar, mes a mes', width='12', model='crm.lead',
             since='19.0.8.0.0', sequence=115, domain=d(OPP, ARCHIVED, INVITATIONS), groupby='create_date',
             interval='month', table_transpose=True, row_label='Mes de creación',
             subtitle='Clic en un número para ver las oportunidades.', measures=[
                 m('Invitaciones a cotizar', 'invitaciones', value_format='integer'),
                 m('Atendidos nuevos (Sin recompra)', 'sr', value_format='integer',
                   extra_domain="[('report_invitation_status', '=', 'atendido_sin_recompra')]"),
                 m('% atendidos nuevos', 'sr_pct', formula='div(sr, invitaciones)', value_format='percent'),
                 m('Atendidos recompra', 'rc', value_format='integer',
                   extra_domain="[('report_invitation_status', '=', 'atendido_recompra')]"),
                 m('% atendidos recompra', 'rc_pct', formula='div(rc, invitaciones)', value_format='percent'),
                 m('Atendidos otros (inadecuado / sin segmento)', 'otros', value_format='integer',
                   extra_domain="[('report_invitation_status', 'in', ['atendido_inadecuado', "
                                "'atendido_sin_segmento'])]"),
                 m('% atendidos otros', 'otros_pct', formula='div(otros, invitaciones)', value_format='percent'),
                 m('No atendidos', 'na', value_format='integer',
                   extra_domain="[('report_invitation_status', '=', 'no_atendido')]"),
                 m('% no atendidos', 'na_pct', formula='div(na, invitaciones)', value_format='percent'),
             ]),
        dict(type='section', name='Ganados, perdidos y venta'),
        dict(type='chart', name='Ganados y perdidos por mes de cierre', width='6', model='crm.lead',
             domain=d(OPP, ARCHIVED, "('report_close_status', '!=', False)"), groupby='date_closed',
             interval='month', groupby2='report_close_status', chart_type='bar_stacked',
             map={'periodo': 'date_closed'}, measures=[m('Cotizaciones', 'cotizaciones')]),
        dict(type='chart', name='Venta por mes de cierre', width='6', model='crm.lead',
             domain=d(OPP, "('won_status', '=', 'won')", NOT_EXCLUDED), groupby='date_closed', interval='month',
             groupby2='report_segment', chart_type='bar_stacked', map={'periodo': 'date_closed'},
             measures=[m('Venta', 'venta', 'sum', 'expected_revenue', value_format='monetary')]),
        # 19.0.8.0.0: venta (barras) contra la meta mensual configurable (línea)
        dict(type='chart', name='Venta por mes de cierre vs meta mensual', width='12', model='crm.lead',
             since='19.0.8.0.0', sequence=141, domain=d(OPP, "('won_status', '=', 'won')", NOT_EXCLUDED),
             groupby='date_closed', interval='month', chart_type='bar', map={'periodo': 'date_closed'},
             subtitle='La meta se captura en CRM › Configuración › Metas de venta mensuales.', measures=[
                 m('Venta ganada', 'venta', 'sum', 'expected_revenue', value_format='monetary', color='#2F5BEA'),
                 m('Meta mensual', 'meta', 'sum', 'amount', source_model=GOAL, source_groupby_field='date',
                   value_format='monetary', color='#F59E0B', series_type='line'),
             ]),
        dict(type='chart', name='Razones de pérdida', width='6', model='crm.lead',
             domain=d(OPP, "('active', '=', False)", "('won_status', '=', 'lost')"), groupby='lost_reason_id',
             chart_type='hbar', sort_mode='value_desc', map={'periodo': 'date_closed'}, show_legend=False,
             measures=[m('Perdidos', 'perdidos')]),
        dict(type='chart', name='Prospección Sin recompra por etapa', width='6', model='crm.lead',
             domain=d(OPP, ARCHIVED, "('report_segment', '=', 'sin_recompra')",
                      "('report_stage_group', 'in', ['prospeccion', 'por_enviar', 'declinado'])"),
             groupby='create_date', interval='month', groupby2='stage_id', chart_type='bar_stacked',
             subtitle='por mes de creación', measures=[m('Oportunidades', 'oportunidades')]),
        # ---------------- Embudo ----------------
        dict(type='section', name='Embudo por segmento'),
        dict(type='table', name='Embudo por segmento (periodo seleccionado)', width='12', model='crm.lead',
             domain=d(OPP, ARCHIVED), groupby='report_segment', row_label='Segmento',
             subtitle='Invitaciones por fecha de creación; ganados y perdidos por fecha de cierre.',
             measures=[
                 m('Invitaciones', 'invitaciones', extra_domain=d(INVITATIONS), value_format='integer'),
                 m('Atendidos', 'atendidos', extra_domain=d(ATTENDED), value_format='integer'),
                 m('Declinados', 'declinados', extra_domain="[('report_invitation_status', '=', 'no_atendido')]",
                   value_format='integer'),
                 m('Ganados', 'ganados', extra_domain=d(WON), period_field='date_closed', value_format='integer'),
                 m('Perdidos', 'perdidos', extra_domain=d(LOST), period_field='date_closed', value_format='integer'),
                 m('Pendientes', 'pendientes', formula='atendidos - ganados - perdidos', value_format='integer'),
                 m('% bateo', 'bateo', formula='div(ganados, atendidos)', value_format='percent'),
                 m('Efectividad', 'efectividad', formula='div(ganados, ganados + perdidos)', value_format='percent'),
             ]),
        # 19.0.8.0.0: antigüedad del pipeline enviado por rangos de días desde la creación
        dict(type='section', name='Pipeline abierto por antigüedad', since='19.0.8.0.0', sequence=190),
        dict(type='chart', name='Antigüedad del pipeline enviado', width='6', model='crm.lead',
             since='19.0.8.0.0', sequence=200, domain=d(OPP, *SENT_PENDING), range_field='create_date',
             range_bounds='30,60,90,180', chart_type='bar', map={'periodo': None},
             subtitle='días desde la creación, hoy; barras = oportunidades, línea = monto', measures=[
                 m('Oportunidades', 'oportunidades', value_format='integer', color='#2F5BEA'),
                 m('Monto', 'monto', 'sum', 'expected_revenue', value_format='monetary', color='#F59E0B',
                   series_type='line', right_axis=True),
             ]),
        dict(type='table', name='Pipeline enviado por rango de días', width='6', model='crm.lead',
             since='19.0.8.0.0', sequence=210, domain=d(OPP, *SENT_PENDING), range_field='create_date',
             range_bounds='30,60,90,180', row_label='Días desde la creación', map={'periodo': None},
             measures=[
                 m('Oportunidades', 'oportunidades', value_format='integer'),
                 m('Monto', 'monto', 'sum', 'expected_revenue', value_format='monetary'),
                 m('% del monto', 'pct', formula='div(monto, pipeline)', value_format='percent'),
             ]),
    ],
}

# ---------------------------------------------------------------------------
# Listados comerciales (19.0.9.0.0): una sección por lámina del Reporte
# Comercial (4b a 9): indicadores Sin Recompra / Recompra, gráfica y listado.
# "Sin Recompra" incluye Inadecuado y sin segmento (como el reporte de
# Mauricio); "Recompra" es solo el segmento Recompra.
# ---------------------------------------------------------------------------
SR = "('report_segment', '!=', 'recompra')"
R = "('report_segment', '=', 'recompra')"
WON_D = (OPP, ARCHIVED, "('won_status', '=', 'won')", NOT_EXCLUDED)
LOST_D = (OPP, "('active', '=', False)", "('won_status', '=', 'lost')")
CANCEL_D = (OPP, ARCHIVED, "('stage_id.report_close_on_enter', '=', True)")
PAUSE_D = (OPP, "('report_open_status', '=', 'pausa')", "('won_status', '=', 'pending')")
WITH_AMOUNT = "('expected_revenue', '>', 0)"
SENT_D = (OPP,) + SENT_PENDING
TO_SEND_D = (OPP, "('report_stage_group', '=', 'por_enviar')", "('won_status', '=', 'pending')",
             "('stage_id.report_close_on_enter', '=', False)")
OLDER_180 = "('create_date', '<', (context_today() - relativedelta(days=180)).strftime('%Y-%m-%d'))"
LAST_3_MONTHS = "('create_date', '>=', (context_today() - relativedelta(months=2)).strftime('%Y-%m-01'))"
PROSPECTING_D = (OPP, ARCHIVED, "('report_segment', '=', 'sin_recompra')",
                 "('report_stage_group', 'in', ['prospeccion', 'por_enviar', 'declinado'])")
REVENUE = 'expected_revenue'
V9 = '19.0.9.0.0'


def segment_kpis(prefix, label, base, period, sequence, color, amount_note=True):
    """Indicadores "<label> Sin Recompra", "<label> Recompra" y el total, cada uno
    con número · monto. Los montos van en indicadores ocultos (<código>_monto)."""
    items = []
    for i, (suffix, title, extra) in enumerate((('_sr', 'Sin Recompra', (SR,)), ('_r', 'Recompra', (R,)),
                                                ('', 'Total', ()))):
        code = prefix + suffix
        domain = d(*(base + extra))
        items += [
            dict(type='kpi', name='%s %s' % (label, title) if suffix else '%s · total' % label, code=code,
                 width='4', model='crm.lead', domain=domain, map={'periodo': period}, since=V9,
                 sequence=sequence + i * 2, measures=[m(title, code)], value_format='integer', abbreviate=False,
                 secondary_code=code + '_monto', color=color,
                 subtitle='proyectos · monto' if amount_note else False),
            dict(type='kpi', name='%s %s (monto)' % (label, title), code=code + '_monto', hidden=True,
                 model='crm.lead', domain=domain, map={'periodo': period}, since=V9, sequence=sequence + i * 2 + 1,
                 measures=[m('Monto', code + '_monto', 'sum', REVENUE)], value_format='monetary'),
        ]
    return items


def hidden_kpi(name, code, domain, period, sequence, aggregate='count', field=None, value_format='integer',
               formula=None):
    item = dict(type='kpi', name=name, code=code, hidden=True, since=V9, sequence=sequence,
                value_format=value_format, abbreviate=value_format not in ('number', 'number1'))
    if formula:
        item['formula'] = formula
    else:
        item.update(model='crm.lead', domain=domain, map={'periodo': period},
                    measures=[m(name, code, aggregate, field)])
    return item


LIST_COLUMNS = 'partner_id, name, report_segment, user_id, expected_revenue'
COMMERCIAL_LISTS = {
    'xmlid': 'dashboard_commercial_lists',
    'name': 'Listados comerciales',
    'category': 'Comercial',
    'sequence': 20,
    'groups': ['sales_team.group_sale_salesman'],
    'description': 'Como el Reporte Comercial: ganados, perdidos, cancelados, en pausa, pipeline abierto y '
                   'prospección, cada uno con indicadores Sin Recompra / Recompra, gráfica y listado. Sin Recompra '
                   'incluye Inadecuado. Clic en un renglón para abrir la oportunidad.',
    'filters': [
        dict(key='periodo', name='Periodo', filter_type='date', field_name='date_closed',
             default_period='this_year'),
        dict(key='vendedor', name='Vendedor', filter_type='many2one', field_name='user_id', comodel='res.users',
             multiple=True, record_domain="[('share', '=', False)]"),
        dict(key='buscar', name='Cliente u oportunidad', filter_type='text', field_name='partner_id'),
    ],
    'widgets': [
        # ================= 4. Proyectos ganados =================
        dict(type='section', name='Proyectos ganados', since=V9, sequence=100,
             subtitle='Por fecha de cierre · semanas = fecha de cierre − fecha de creación'),
        dict(type='kpi', name='Ganados Sin Recompra', code='ganados_sr', width='3', model='crm.lead',
             domain=d(*(WON_D + (SR,))), map={'periodo': 'date_closed'}, since=V9, sequence=102,
             measures=[m('Ganados', 'ganados_sr')], value_format='integer', abbreviate=False,
             secondary_code='venta_sr', subtitle='ticket {ticket_sr} · {semanas_sr} semanas promedio',
             color='#EFF6FF'),
        dict(type='kpi', name='Ganados Recompra', code='ganados_r', width='3', model='crm.lead',
             domain=d(*(WON_D + (R,))), map={'periodo': 'date_closed'}, since=V9, sequence=103,
             measures=[m('Ganados', 'ganados_r')], value_format='integer', abbreviate=False,
             secondary_code='venta_r', subtitle='ticket {ticket_r} · {semanas_r} semanas promedio',
             color='#EFF6FF'),
        dict(type='kpi', name='Venta ganada', code='venta', width='3', model='crm.lead', domain=d(*WON_D),
             map={'periodo': 'date_closed'}, since=V9, sequence=104,
             measures=[m('Venta', 'venta', 'sum', REVENUE)], value_format='monetary',
             subtitle='{ganados} proyectos · ticket promedio {ticket}', color='#EFF6FF'),
        dict(type='kpi', name='Semanas creación→cierre', code='semanas', width='3', model='crm.lead',
             domain=d(*WON_D), map={'periodo': 'date_closed'}, since=V9, sequence=105,
             measures=[m('Semanas', 'semanas', 'avg', 'report_close_weeks')], value_format='number1',
             abbreviate=False, subtitle='promedio · SR {semanas_sr} · R {semanas_r}', color='#F9FAFB'),
        hidden_kpi('Venta Sin Recompra', 'venta_sr', d(*(WON_D + (SR,))), 'date_closed', 106, 'sum', REVENUE,
                   'monetary'),
        hidden_kpi('Venta Recompra', 'venta_r', d(*(WON_D + (R,))), 'date_closed', 107, 'sum', REVENUE, 'monetary'),
        hidden_kpi('Ganados (todos)', 'ganados', d(*WON_D), 'date_closed', 108),
        hidden_kpi('Semanas SR', 'semanas_sr', d(*(WON_D + (SR,))), 'date_closed', 109, 'avg', 'report_close_weeks',
                   'number1'),
        hidden_kpi('Semanas R', 'semanas_r', d(*(WON_D + (R,))), 'date_closed', 110, 'avg', 'report_close_weeks',
                   'number1'),
        hidden_kpi('Ticket SR', 'ticket_sr', None, None, 111, value_format='monetary',
                   formula='div(venta_sr, ganados_sr)'),
        hidden_kpi('Ticket R', 'ticket_r', None, None, 112, value_format='monetary', formula='div(venta_r, ganados_r)'),
        hidden_kpi('Ticket', 'ticket', None, None, 113, value_format='monetary', formula='div(venta, ganados)'),
        dict(type='list', name='Ganados Sin Recompra', width='6', model='crm.lead', domain=d(*(WON_D + (SR,))),
             map={'periodo': 'date_closed'}, since=V9, sequence=120, height=420, limit=80,
             list_fields='create_date:Creado, date_closed:Cierre, report_close_weeks:Sem, partner_id:Cliente, name:Proyecto, expected_revenue:Monto',
             list_order='date_closed asc', list_show_number=True, list_show_total=True,
             subtitle='Incluye Inadecuado y sin segmento.'),
        dict(type='list', name='Ganados Recompra', width='6', model='crm.lead', domain=d(*(WON_D + (R,))),
             map={'periodo': 'date_closed'}, since=V9, sequence=121, height=420, limit=80,
             list_fields='create_date:Creado, date_closed:Cierre, report_close_weeks:Sem, partner_id:Cliente, name:Proyecto, expected_revenue:Monto',
             list_order='date_closed asc', list_show_number=True, list_show_total=True),
        # ================= 5. Proyectos perdidos =================
        dict(type='section', name='Proyectos perdidos', since=V9, sequence=200,
             subtitle='Qué estamos dejando ir · por fecha de cierre · razón de pérdida capturada en Odoo'),
    ] + segment_kpis('perdidos', 'Perdidos', LOST_D, 'date_closed', 202, '#FEF2F2') + [
        dict(type='chart', name='Razones de pérdida ({perdidos} proyectos · {perdidos_monto})', width='4',
             model='crm.lead', domain=d(*LOST_D), groupby='lost_reason_id', chart_type='hbar',
             sort_mode='value_desc', map={'periodo': 'date_closed'}, show_legend=False, show_values=True,
             since=V9, sequence=220, height=380, measures=[m('Perdidos', 'perdidos', color='#DC4B4B')]),
        dict(type='list', name='Perdidos por monto', width='8', model='crm.lead', domain=d(*LOST_D),
             map={'periodo': 'date_closed'}, since=V9, sequence=221, height=380, limit=30,
             list_fields='date_closed:Cierre, partner_id:Cliente, name:Proyecto, report_segment:SR/R, expected_revenue:Monto, lost_reason_id:Razón',
             list_order='expected_revenue desc', list_show_number=True, list_show_total=True),
        # ================= 6. Proyectos cancelados =================
        dict(type='section', name='Proyectos cancelados', since=V9, sequence=300,
             subtitle='Cotizados que el cliente canceló o no ejecutó · por fecha de creación del lead'),
    ] + segment_kpis('cancelados', 'Cancelados', CANCEL_D, 'create_date', 302, '#F1F5F9') + [
        dict(type='chart', name='Cancelados por mes de creación ({cancelados} proyectos · {cancelados_monto})',
             width='4', model='crm.lead', domain=d(*CANCEL_D), groupby='create_date', interval='month',
             chart_type='bar', map={'periodo': 'create_date'}, show_legend=False, show_values=True, since=V9,
             sequence=320, height=380, measures=[m('Cancelados', 'cancelados', color='#94A3B8')]),
        dict(type='list', name='Cancelados por monto', width='8', model='crm.lead', domain=d(*CANCEL_D),
             map={'periodo': 'create_date'}, since=V9, sequence=321, height=380, limit=30,
             list_fields='create_date:Creado, partner_id:Cliente, name:Proyecto, report_segment:SR/R, expected_revenue:Monto',
             list_order='expected_revenue desc', list_show_number=True, list_show_total=True),
        # ================= 7. Proyectos en pausa =================
        dict(type='section', name='Proyectos en pausa', since=V9, sequence=400,
             subtitle='Cotizaciones que el cliente pospuso · solo con monto · a hoy · días desde la creación '
                      '(rojo: más de un año)'),
    ] + segment_kpis('pausa', 'En pausa', PAUSE_D + (WITH_AMOUNT,), None, 402, '#FFFBEB') + [
        dict(type='chart', name='En pausa por antigüedad ({pausa} proyectos · {pausa_monto})', width='4',
             model='crm.lead', domain=d(*(PAUSE_D + (WITH_AMOUNT,))), range_field='create_date',
             range_bounds='90,180,365', chart_type='bar', map={'periodo': None}, show_legend=False,
             show_values=True, since=V9, sequence=420, height=380,
             measures=[m('Proyectos', 'proyectos', color='#E0A526')]),
        dict(type='list', name='En pausa por monto', width='8', model='crm.lead', domain=d(*(PAUSE_D + (WITH_AMOUNT,))),
             map={'periodo': None}, since=V9, sequence=421, height=380, limit=30,
             list_fields='create_date:Creado, report_age_days:Días, partner_id:Cliente, name:Proyecto, report_segment:SR/R, expected_revenue:Monto',
             list_order='expected_revenue desc', list_highlight='report_age_days > 365', list_show_number=True,
             list_show_total=True),
        # ================= 8. Pipeline abierto =================
        dict(type='section', name='Pipeline abierto', since=V9, sequence=500,
             subtitle='Situación a hoy · antigüedad = días desde la creación del lead (rojo: más de 90 días)'),
        dict(type='kpi', name='Enviadas (pendientes de respuesta)', code='env', width='3', model='crm.lead',
             domain=d(*SENT_D), map={'periodo': None}, since=V9, sequence=502, measures=[m('Enviadas', 'env')],
             value_format='integer', abbreviate=False, secondary_code='env_monto',
             subtitle='SR {env_sr} ({env_sr_monto}) · R {env_r} ({env_r_monto})', color='#EFF6FF'),
        hidden_kpi('Enviadas (monto)', 'env_monto', d(*SENT_D), None, 503, 'sum', REVENUE, 'monetary'),
        hidden_kpi('Enviadas SR', 'env_sr', d(*(SENT_D + (SR,))), None, 504),
        hidden_kpi('Enviadas SR (monto)', 'env_sr_monto', d(*(SENT_D + (SR,))), None, 505, 'sum', REVENUE, 'monetary'),
        hidden_kpi('Enviadas R', 'env_r', d(*(SENT_D + (R,))), None, 506),
        hidden_kpi('Enviadas R (monto)', 'env_r_monto', d(*(SENT_D + (R,))), None, 507, 'sum', REVENUE, 'monetary'),
        dict(type='kpi', name='Por enviar (invitación / cotizando / revisión)', code='por_enviar', width='3',
             model='crm.lead', domain=d(*TO_SEND_D), map={'periodo': None}, since=V9, sequence=508,
             measures=[m('Por enviar', 'por_enviar')], value_format='integer', abbreviate=False,
             subtitle='{por_enviar_monto} estimado', color='#F9FAFB'),
        hidden_kpi('Por enviar (monto)', 'por_enviar_monto', d(*TO_SEND_D), None, 509, 'sum', REVENUE, 'monetary'),
        dict(type='kpi', name='En pausa', code='pausa_todos', width='3', model='crm.lead', domain=d(*PAUSE_D),
             map={'periodo': None}, since=V9, sequence=510, measures=[m('En pausa', 'pausa_todos')],
             value_format='integer', abbreviate=False, secondary_code='pausa_todos_monto',
             subtitle='proyectos pospuestos por el cliente', color='#F9FAFB'),
        hidden_kpi('En pausa (monto)', 'pausa_todos_monto', d(*PAUSE_D), None, 511, 'sum', REVENUE, 'monetary'),
        dict(type='kpi', name='Enviadas con más de 180 días', code='env_180', width='3', model='crm.lead',
             domain=d(*(SENT_D + (OLDER_180,))), map={'periodo': None}, since=V9, sequence=512,
             measures=[m('Enviadas > 180 días', 'env_180')], value_format='integer', abbreviate=False,
             secondary_code='env_180_monto', subtitle='candidatas a depurar o reactivar', color='#FFF7ED'),
        hidden_kpi('Enviadas > 180 días (monto)', 'env_180_monto', d(*(SENT_D + (OLDER_180,))), None, 513, 'sum',
                   REVENUE, 'monetary'),
        dict(type='chart', name='Antigüedad de cotizaciones enviadas (# y monto)', width='6', model='crm.lead',
             domain=d(*SENT_D), range_field='create_date', range_bounds='30,60,90,180', chart_type='bar',
             map={'periodo': None}, show_values=True, since=V9, sequence=520, height=340, measures=[
                 m('Cotizaciones', 'cotizaciones', value_format='integer', color='#2F5BEA'),
                 m('Monto', 'monto', 'sum', REVENUE, value_format='monetary', color='#F59E0B',
                   series_type='line', right_axis=True),
             ]),
        dict(type='table', name='Enviadas por rango de días', width='6', model='crm.lead', domain=d(*SENT_D),
             range_field='create_date', range_bounds='30,60,90,180', row_label='Rango', map={'periodo': None},
             since=V9, sequence=521, height=340, measures=[
                 m('#', 'cotizaciones', value_format='integer'),
                 m('Monto', 'monto', 'sum', REVENUE, value_format='monetary'),
                 m('% del monto', 'pct', formula='div(monto, env_monto)', value_format='percent'),
             ]),
        dict(type='list', name='Cotizaciones enviadas por monto', width='12', model='crm.lead', domain=d(*SENT_D),
             map={'periodo': None}, since=V9, sequence=530, height=420, limit=30,
             list_fields='create_date:Creado, report_age_days:Días, partner_id:Cliente, name:Proyecto, report_segment:SR/R, user_id:Vendedor, expected_revenue:Monto',
             list_order='expected_revenue desc', list_highlight='report_age_days > 90', list_show_number=True,
             list_show_total=True),
        # ================= 9. Prospección Sin Recompra =================
        dict(type='section', name='Prospección Sin Recompra', since=V9, sequence=600,
             subtitle='Trabajo comercial previo a la cotización · por mes de creación y etapa del embudo'),
        hidden_kpi('Prospección (leads)', 'prospeccion', d(*PROSPECTING_D), 'create_date', 601),
        dict(type='chart', name='Prospección Sin Recompra: {prospeccion} leads', width='6', model='crm.lead',
             domain=d(*PROSPECTING_D), groupby='create_date', interval='month', groupby2='stage_id',
             chart_type='bar_stacked', map={'periodo': 'create_date'}, show_values=True, since=V9, sequence=610,
             height=460, subtitle='por mes de creación', measures=[m('Leads', 'leads')]),
        dict(type='list', name='Leads de los últimos 3 meses', width='6', model='crm.lead',
             domain=d(*(PROSPECTING_D + (LAST_3_MONTHS,))), map={'periodo': None}, since=V9, sequence=611,
             height=460, limit=100, list_group_field='stage_id', list_order='create_date desc',
             list_fields='create_date:Creado, partner_id:Cliente, name:Proyecto, x_studio_cmo_se_gener_el_lead:Origen',
             subtitle='Agrupados por etapa; el periodo no aplica (siempre los últimos 3 meses).'),
        # ================= Seguimiento =================
        dict(type='section', name='Seguimiento', since=V9, sequence=690,
             subtitle='Oportunidades abiertas con más tiempo sin movimiento'),
        dict(type='list', name='Oportunidades lentas (más tiempo sin movimiento)', width='12', model='crm.lead',
             sequence=700,
             domain=d(OPP, "('won_status', '=', 'pending')",
                      "('report_stage_group', 'in', ['prospeccion', 'por_enviar', 'cotizado'])",
                      "('stage_id.report_close_on_enter', '=', False)"),
             map={'periodo': None}, list_fields='report_last_move_date, partner_id, name, stage_id, user_id',
             list_order='report_last_move_date asc', limit=15),
    ],
}

# Listados de la versión 19.0.6.0.0 que reemplaza la 19.0.9.0.0
OLD_LIST_NAMES = [
    'Proyectos ganados (más recientes)', 'Proyectos perdidos (mayor monto)',
    'Pipeline abierto: enviadas pendientes de respuesta', 'Proyectos en pausa', 'Proyectos cancelados',
]


PARTIDA = 'business.report.week.partida'
PROJECT = 'business.report.week.project'
WEEK_REPORT = {
    'xmlid': 'dashboard_week_report',
    'name': 'Reporte semanal Dirección',
    'category': 'Dirección',
    'sequence': 30,
    'groups': ['project.group_project_user'],
    'description': 'Proyectos en curso. Por omisión muestra la semana vigente (la última cerrada); elige otra '
                   'semana en el filtro. Rojo en el margen = menor a la alerta de la semana.',
    'filters': [
        dict(key='semana', name='Semana', filter_type='many2one', field_name='week_id',
             comodel='business.report.week', multiple=False, required=True,
             default_domain="[('is_current', '=', True)]"),
        dict(key='proyecto', name='Proyecto', filter_type='many2one', field_name='analytic_account_id',
             comodel='account.analytic.account', multiple=True),
    ],
    'widgets': [
        # ---------------- Indicadores ----------------
        dict(type='kpi', name='Costo planeado', code='planeado', width='3', model=PARTIDA,
             measures=[m('Planeado', 'planeado', 'sum', 'planned_amount')], value_format='monetary',
             subtitle='NeoData, Σ partidas', color='#EFF6FF'),
        dict(type='kpi', name='Costo real', code='real', width='3', model=PARTIDA,
             measures=[m('Real', 'real', 'sum', 'real_amount')], value_format='monetary',
             subtitle='Odoo, a la fecha de corte', color='#F9FAFB'),
        dict(type='kpi', name='Desviación acumulada', code='desviacion', width='3', formula='planeado - real',
             value_format='monetary', color_mode='sign', subtitle='planeado − real', color='#F0FDF4'),
        dict(type='kpi', name='% de optimización', code='optimizacion', width='3',
             formula='div(desviacion, planeado)', value_format='percent', color_mode='sign',
             subtitle='desviación / planeado', color='#F0FDF4'),
        dict(type='kpi', name='Δ planeado', code='delta_planeado', hidden=True, model=PARTIDA,
             measures=[m('Δ planeado', 'delta_planeado', 'sum', 'planned_delta')]),
        dict(type='kpi', name='Δ real', code='delta_real', hidden=True, model=PARTIDA,
             measures=[m('Δ real', 'delta_real', 'sum', 'real_delta')]),
        dict(type='kpi', name='Desviación vs semana anterior', code='delta_desviacion', width='3',
             formula='delta_planeado - delta_real', value_format='monetary', color_mode='sign',
             subtitle='cambio de la desviación', color='#F0FDF4'),
        dict(type='kpi', name='Venta semanal', code='venta_semanal', width='3', model=PROJECT,
             measures=[m('Venta semanal', 'venta_semanal', 'sum', 'neodata_advance')], value_format='monetary',
             subtitle='Σ avance NeoData', color='#FFF7ED'),
        dict(type='kpi', name='Venta real', code='venta_real', hidden=True, model=PROJECT,
             measures=[m('Venta real', 'venta_real', 'sum', 'estimate_amount')]),
        dict(type='kpi', name='Costo real proyectos', code='costo_proyectos', hidden=True, model=PROJECT,
             measures=[m('Costo', 'costo_proyectos', 'sum', 'real_total')]),
        dict(type='kpi', name='Alerta de margen', code='alerta', hidden=True, model='business.report.week',
             map={'semana': 'id', 'proyecto': None},
             measures=[m('Alerta', 'alerta', 'max', 'margin_alert_pct')]),
        dict(type='kpi', name='Margen operativo', code='margen', width='3', formula='venta_real - costo_proyectos',
             value_format='monetary', color_mode='sign', subtitle='estimado autorizado − costo real',
             color='#F0FDF4'),
        dict(type='kpi', name='% margen operativo', code='margen_pct', width='3',
             formula='div(margen, venta_real)', value_format='percent', color_mode='threshold', threshold='alerta',
             subtitle='rojo si es menor a la alerta de la semana', color='#F0FDF4'),
        # ---------------- Gráficas ----------------
        dict(type='chart', name='Balance de costos por partida', width='6', model=PARTIDA, groupby='partida',
             chart_type='bar', measures=[
                 m('Planeado (NeoData)', 'planeado', 'sum', 'planned_amount', color='#2F5BEA', value_format='monetary'),
                 m('Real (Odoo)', 'real', 'sum', 'real_amount', color='#E8556F', value_format='monetary')]),
        dict(type='chart', name='Indicadores de costos y venta por semana', width='6', model=PROJECT,
             groupby='week_date', interval='day', chart_type='line', map={'semana': None},
             subtitle='todas las semanas', measures=[
                 m('Balance de costos (planeado − real)', 'balance', 'sum', 'deviation', color='#2F5BEA',
                   value_format='monetary'),
                 m('Venta semanal (avance NeoData)', 'venta', 'sum', 'neodata_advance', color='#F59E0B')]),
        # ---------------- Tablas ----------------
        dict(type='table', name='Balance de costos por partida (Σ proyectos en análisis)', width='12',
             model=PARTIDA, groupby='partida', row_label='Partida', measures=[
                 m('Planeado', 'planeado', 'sum', 'planned_amount', value_format='monetary'),
                 m('Real', 'real', 'sum', 'real_amount', value_format='monetary'),
                 m('Diferencia', 'diferencia', formula='planeado - real', value_format='monetary', color_mode='sign'),
                 m('%', 'pct', formula='div(diferencia, planeado)', value_format='percent', color_mode='sign'),
                 m('Δ planeado vs sem. ant.', 'delta_planeado', 'sum', 'planned_delta', value_format='monetary'),
                 m('Δ real vs sem. ant.', 'delta_real', 'sum', 'real_delta', value_format='monetary')]),
        dict(type='table', name='Margen operativo al momento – proyectos', width='12', model=PROJECT,
             groupby='analytic_account_id', row_label='Proyecto', total_first=True,
             drilldown_view='custom_business_reports.business_report_week_project_view_form_detail',
             measures=[
                 m('Venta real', 'venta', 'sum', 'estimate_amount', value_format='monetary'),
                 m('Costo real', 'costo', 'sum', 'real_total', value_format='monetary'),
                 m('Margen operativo', 'margen', formula='venta - costo', value_format='monetary'),
                 m('% margen', 'pct', formula='div(margen, venta)', value_format='percent',
                   color_mode='threshold', threshold='alerta')]),
        dict(type='list', name='Proyectos en análisis', width='12', model=PROJECT, limit=30,
             drilldown_view='custom_business_reports.business_report_week_project_view_form_detail',
             list_fields='analytic_account_id, contract_amount, estimate_amount, invoiced_amount, neodata_sale, '
                         'planned_total, real_total, deviation, operating_margin',
             list_order='sequence, id'),
    ],
}

DEFAULT_DASHBOARDS = [COMMERCIAL, COMMERCIAL_LISTS, WEEK_REPORT]
MODULE = 'custom_business_reports'


def _setup_dashboards(env, specs=None):
    """Crea los tableros de fábrica que no existan todavía."""
    created = []
    for spec in specs or DEFAULT_DASHBOARDS:
        xmlid = '%s.%s' % (MODULE, spec['xmlid'])
        if env.ref(xmlid, raise_if_not_found=False):
            continue
        dashboard = _create_dashboard(env, spec)
        env['ir.model.data']._update_xmlids([{'xml_id': xmlid, 'record': dashboard, 'noupdate': True}])
        created.append(dashboard.name)
    _logger.info('Tableros creados: %s', created)
    return created


def _create_dashboard(env, spec):
    Model = env['ir.model']
    groups = [env.ref(xmlid).id for xmlid in spec.get('groups', []) if env.ref(xmlid, raise_if_not_found=False)]
    dashboard = env['business.dashboard'].create({
        'name': spec['name'], 'category': spec.get('category'), 'sequence': spec.get('sequence', 10),
        'description': spec.get('description'), 'group_ids': [(6, 0, groups)],
    })
    filters = {}
    for seq, flt in enumerate(spec['filters']):
        vals = {key: value for key, value in flt.items()
                if key not in ('key', 'comodel', 'selection_model')}
        vals.update(dashboard_id=dashboard.id, sequence=seq * 10)
        if flt.get('comodel'):
            vals['comodel_id'] = Model._get_id(flt['comodel'])
        if flt.get('selection_model'):
            vals['selection_model_id'] = Model._get_id(flt['selection_model'])
        filters[flt['key']] = env['business.dashboard.filter'].create(vals)
    seq = 0
    for item in spec['widgets']:
        if 'sequence' not in item:      # los elementos con secuencia fija no recorren a los demás
            seq += 10
        _create_widget(env, dashboard, filters, item, item.get('sequence', seq))
    return dashboard


def _ensure_widgets(env, specs=None, since=None, xmlids=None):
    """Agrega a los tableros que ya existen los elementos nuevos de fábrica.

    Solo los elementos marcados con 'since' (= since, si se indica) y que no
    existan ya con el mismo título; así no se duplican ni se tocan los que el
    usuario cambió o borró a propósito antes de la actualización.
    """
    added = []
    for spec in specs or DEFAULT_DASHBOARDS:
        if xmlids and spec['xmlid'] not in xmlids:
            continue
        dashboard = env.ref('%s.%s' % (MODULE, spec['xmlid']), raise_if_not_found=False)
        if not dashboard:
            continue
        existing = set(dashboard.with_context(lang='en_US').widget_ids.mapped('name')) | \
            set(dashboard.widget_ids.mapped('name'))
        filters = {}
        for flt in spec['filters']:
            match = dashboard.filter_ids.filtered(lambda f, flt=flt: f.name == flt['name']) or \
                dashboard.filter_ids.filtered(lambda f, flt=flt: f.field_name == flt.get('field_name')
                                              and f.filter_type == flt['filter_type'])
            if match:
                filters[flt['key']] = match[:1]
        for item in spec['widgets']:
            if not item.get('since') or (since and item['since'] != since) or item['name'] in existing:
                continue
            item = dict(item, map={key: path for key, path in item.get('map', {}).items() if key in filters})
            _create_widget(env, dashboard, filters, item, item.get('sequence', 1000))
            added.append('%s: %s' % (dashboard.name, item['name']))
    _logger.info('Elementos de tablero agregados: %s', added)
    return added


def _create_widget(env, dashboard, filters, item, sequence):
    Fields = env['ir.model.fields']
    model = item.get('model')
    vals = {
        'dashboard_id': dashboard.id, 'sequence': sequence, 'name': item['name'],
        'widget_type': item['type'], 'width': item.get('width', '12'), 'code': item.get('code'),
        'subtitle': item.get('subtitle'), 'hidden': item.get('hidden', False),
        'domain': item.get('domain', '[]'), 'formula': item.get('formula'),
        'value_format': item.get('value_format', 'number'), 'abbreviate': item.get('abbreviate', True),
        'color_mode': item.get('color_mode', 'none'), 'threshold': item.get('threshold'),
        'color': item.get('color', '#FFFFFF' if item['type'] != 'kpi' else '#F9FAFB'),
        'chart_type': item.get('chart_type', 'bar'), 'show_legend': item.get('show_legend', True),
        'groupby_interval': item.get('interval', 'month'), 'sort_mode': item.get('sort_mode', 'group'),
        'limit': item.get('limit', 0), 'row_label': item.get('row_label'),
        'total_first': item.get('total_first', False), 'list_fields': item.get('list_fields'),
        'list_order': item.get('list_order'), 'height': item.get('height', 320),
        'table_transpose': item.get('table_transpose', False),
        'range_bounds': item.get('range_bounds', '30,60,90,180'),
        # 19.0.9.0.0
        'secondary_code': item.get('secondary_code'), 'show_values': item.get('show_values', False),
        'list_show_number': item.get('list_show_number', False),
        'list_show_total': item.get('list_show_total', False),
        'list_highlight': item.get('list_highlight'),
    }
    if model and item.get('list_fields'):
        # Los campos que no existen en esta base (p. ej. de Studio) se omiten
        parts = [part.strip() for part in item['list_fields'].split(',')]
        vals['list_fields'] = ', '.join(part for part in parts if part.partition(':')[0].strip() in env[model]._fields)
    if model and item.get('list_group_field') in env[model]._fields:
        vals['list_group_field'] = item['list_group_field']
    if model:
        vals['model_id'] = env['ir.model']._get_id(model)
        if item.get('groupby'):
            vals['groupby_field_id'] = Fields._get(model, item['groupby']).id
        if item.get('groupby2'):
            vals['groupby2_field_id'] = Fields._get(model, item['groupby2']).id
        if item.get('range_field'):
            vals['range_field_id'] = Fields._get(model, item['range_field']).id
    if item.get('drilldown_view'):
        view = env.ref(item['drilldown_view'], raise_if_not_found=False)
        vals['drilldown_view_id'] = view.id if view else False
    vals['measure_ids'] = [(0, 0, {
        'sequence': i * 10, 'name': ms['name'], 'code': ms['code'], 'aggregate': ms['aggregate'],
        'field_id': Fields._get(ms.get('source_model') or model, ms['field']).id if ms.get('field') else False,
        'source_model_id': env['ir.model']._get_id(ms['source_model']) if ms.get('source_model') else False,
        'source_groupby_field': ms.get('source_groupby_field'),
        'series_type': ms.get('series_type') or False, 'right_axis': ms.get('right_axis', False),
        'extra_domain': ms.get('extra_domain'), 'period_field': ms.get('period_field'),
        'formula': ms.get('formula'), 'value_format': ms.get('value_format', item.get('value_format', 'number')),
        'color_mode': ms.get('color_mode', 'none'), 'threshold': ms.get('threshold'),
        'color': ms.get('color'), 'hidden': ms.get('hidden', False),
    }) for i, ms in enumerate(item.get('measures', []))]
    vals['filter_map_ids'] = [(0, 0, {'filter_id': filters[key].id, 'field_path': path or False})
                              for key, path in item.get('map', {}).items()]
    return env['business.dashboard.widget'].create(vals)


def _upgrade_commercial_lists(env):
    """19.0.9.0.0: rearma "Listados comerciales" como el Reporte Comercial.

    Quita los 5 listados de fábrica anteriores (se reemplazan por secciones con
    indicadores, gráfica y listado), agrega los elementos nuevos y deja
    "Oportunidades lentas" al final. Lo que el usuario haya agregado se queda.
    """
    dashboard = env.ref('%s.%s' % (MODULE, COMMERCIAL_LISTS['xmlid']), raise_if_not_found=False)
    if not dashboard:
        return []
    old = dashboard.widget_ids.filtered(lambda w: w.widget_type == 'list' and w.name in OLD_LIST_NAMES)
    old.unlink()
    period = dashboard.filter_ids.filtered(lambda f: f.name == 'Periodo (cierre)')
    period.write({'name': 'Periodo'})
    dashboard.description = COMMERCIAL_LISTS['description']
    slow = dashboard.widget_ids.filtered(lambda w: w.name.startswith('Oportunidades lentas'))
    slow.write({'sequence': 700})
    return _ensure_widgets(env, since=V9, xmlids=[COMMERCIAL_LISTS['xmlid']])
