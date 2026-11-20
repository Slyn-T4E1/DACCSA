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

LIST_COLUMNS = 'partner_id, name, report_segment, user_id, expected_revenue'
COMMERCIAL_LISTS = {
    'xmlid': 'dashboard_commercial_lists',
    'name': 'Listados comerciales',
    'category': 'Comercial',
    'sequence': 20,
    'groups': ['sales_team.group_sale_salesman'],
    'description': 'Oportunidades por estatus. Clic en un renglón para abrirla; "Ver todos" abre la lista completa.',
    'filters': [
        dict(key='periodo', name='Periodo (cierre)', filter_type='date', field_name='date_closed',
             default_period='this_year'),
        dict(key='vendedor', name='Vendedor', filter_type='many2one', field_name='user_id', comodel='res.users',
             multiple=True, record_domain="[('share', '=', False)]"),
        dict(key='buscar', name='Cliente u oportunidad', filter_type='text', field_name='partner_id'),
    ],
    'widgets': [
        dict(type='list', name='Proyectos ganados (más recientes)', width='6', model='crm.lead',
             domain=d(OPP, "('won_status', '=', 'won')", NOT_EXCLUDED),
             list_fields='date_closed, ' + LIST_COLUMNS, list_order='date_closed desc', limit=15),
        dict(type='list', name='Proyectos perdidos (mayor monto)', width='6', model='crm.lead',
             domain=d(OPP, "('active', '=', False)", "('won_status', '=', 'lost')"),
             list_fields='date_closed, partner_id, name, lost_reason_id, expected_revenue',
             list_order='expected_revenue desc', limit=15),
        dict(type='list', name='Pipeline abierto: enviadas pendientes de respuesta', width='6', model='crm.lead',
             domain=d(OPP, "('report_open_status', '=', 'enviada')", "('won_status', '=', 'pending')"),
             map={'periodo': None}, list_fields='create_date, ' + LIST_COLUMNS + ', report_idle_days',
             list_order='expected_revenue desc', limit=15),
        dict(type='list', name='Proyectos en pausa', width='6', model='crm.lead',
             domain=d(OPP, "('report_open_status', '=', 'pausa')", "('won_status', '=', 'pending')"),
             map={'periodo': None}, list_fields='create_date, ' + LIST_COLUMNS,
             list_order='expected_revenue desc', limit=15),
        dict(type='list', name='Proyectos cancelados', width='6', model='crm.lead',
             domain=d(OPP, "('stage_id.report_close_on_enter', '=', True)"),
             list_fields='date_closed, ' + LIST_COLUMNS, list_order='date_closed desc', limit=15),
        dict(type='list', name='Oportunidades lentas (más tiempo sin movimiento)', width='6', model='crm.lead',
             domain=d(OPP, "('won_status', '=', 'pending')",
                      "('report_stage_group', 'in', ['prospeccion', 'por_enviar', 'cotizado'])",
                      "('stage_id.report_close_on_enter', '=', False)"),
             map={'periodo': None}, list_fields='report_last_move_date, partner_id, name, stage_id, user_id',
             list_order='report_last_move_date asc', limit=15),
    ],
}

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


def _ensure_widgets(env, specs=None, since=None):
    """Agrega a los tableros que ya existen los elementos nuevos de fábrica.

    Solo los elementos marcados con 'since' (= since, si se indica) y que no
    existan ya con el mismo título; así no se duplican ni se tocan los que el
    usuario cambió o borró a propósito antes de la actualización.
    """
    added = []
    for spec in specs or DEFAULT_DASHBOARDS:
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
    }
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
