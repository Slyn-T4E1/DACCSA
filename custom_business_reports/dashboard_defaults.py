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
               formula=None, since=V9):
    item = dict(type='kpi', name=name, code=code, hidden=True, since=since, sequence=sequence,
                value_format=value_format, abbreviate=value_format not in ('number', 'number1'))
    if formula:
        item['formula'] = formula
    else:
        item.update(model='crm.lead', domain=domain, map={'periodo': period},
                    measures=[m(name, code, aggregate, field)])
    return item



# ---------------------------------------------------------------------------
# Seguimiento comercial (19.0.10.0.0): láminas 0 a 4 y 10 del Reporte Comercial.
# Todos los elementos llevan secuencia fija; la migración acomoda los que ya
# existen y agrega los nuevos (since=V10).
# ---------------------------------------------------------------------------
V10 = '19.0.10.0.0'
SALE_D = (OPP, "('won_status', '=', 'won')", NOT_EXCLUDED)
WON_C = (OPP, ARCHIVED, WON)
LOST_C = (OPP, ARCHIVED, LOST)
ATT_C = (OPP, ARCHIVED, ATTENDED)
INV_C = (OPP, ARCHIVED, INVITATIONS)
DECLINED = "('report_invitation_status', '=', 'no_atendido')"
PIPE_D = (OPP,) + SENT_PENDING
ORIGIN = 'x_studio_cmo_se_gener_el_lead'
# 19.0.10.0.0 (domino anterior) y 19.0.10.0.1: como la lámina 10, Sin Recompra incluye Inadecuado, sin
# "Ganados en 0's" y sin los leads sin origen o con origen "Recompra".
OLD_ORIGIN_DOMAIN = d(OPP, ARCHIVED, "('report_segment', '=', 'sin_recompra')")
ORIGIN_DOMAIN = d(OPP, ARCHIVED, SR, NOT_EXCLUDED, "('%s', '!=', False)" % ORIGIN,
                  "('%s', '!=', 'Recompra')" % ORIGIN)
OLD_CUMULATIVE_COLOR, CUMULATIVE_COLOR = '#0B1324', '#64748B'


def _since(days, field):
    return "('%s', '>=', (context_today() - relativedelta(days=%d)).strftime('%%Y-%%m-%%d'))" % (field, days)


QUARTER_START = "context_today().replace(month=(context_today().month - 1) // 3 * 3 + 1, day=1)"
THIS_QUARTER = "('create_date', '>=', %s.strftime('%%Y-%%m-%%d'))" % QUARTER_START
LAST_QUARTER = ("('create_date', '>=', (%s - relativedelta(months=3)).strftime('%%Y-%%m-%%d'))" % QUARTER_START,
                "('create_date', '<', %s.strftime('%%Y-%%m-%%d'))" % QUARTER_START)


def hk(name, code, domain=None, period=False, sequence=60, aggregate='count', field=None, value_format='integer',
       formula=None):
    """Indicador oculto de Seguimiento comercial (period=False: periodo por omisión, create_date)."""
    item = hidden_kpi(name, code, d(*domain) if domain else None, None, sequence, aggregate, field, value_format,
                      formula, since=V10)
    if not formula:
        item['map'] = {} if period is False else {'periodo': period}
    return item


COMMERCIAL = {
    'xmlid': 'dashboard_commercial',
    'name': 'Seguimiento comercial',
    'category': 'Comercial',
    'sequence': 10,
    'groups': ['sales_team.group_sale_salesman'],
    'description': 'Dirección de Nuevos Proyectos, como el Reporte Comercial: resumen ejecutivo, invitaciones a '
                   'cotizar, ganados y perdidos, venta vs meta y origen de leads. Excluye "Ganados en 0\'s". '
                   'Sin Recompra incluye Inadecuado.',
    'filters': [
        dict(key='periodo', name='Periodo', filter_type='date', field_name='create_date', default_period='this_year'),
        dict(key='vendedor', name='Vendedor', filter_type='many2one', field_name='user_id', comodel='res.users',
             multiple=True, record_domain="[('share', '=', False)]"),
        dict(key='segmento', name='Segmento', filter_type='selection', field_name='report_segment',
             selection_model='crm.lead'),
    ],
    'widgets': [
        # ================= Resumen ejecutivo =================
        dict(type='section', name='Resumen ejecutivo', since=V10, sequence=5,
             subtitle='Venta y cierres por fecha de cierre; invitaciones y atendidas por fecha de creación'),
        # Renglón 1
        dict(type='kpi', name='Venta ganada', code='venta', width='3', model='crm.lead', domain=d(*SALE_D),
             map={'periodo': 'date_closed'}, sequence=10,
             measures=[m('Venta', 'venta', 'sum', REVENUE)], value_format='monetary',
             subtitle='{ganados} proyectos · SR {venta_sr} · R {venta_r}', color='#EFF6FF'),
        dict(type='kpi', name='Avance vs meta', code='avance_meta', width='3', since='19.0.8.0.0', sequence=12,
             formula='div(venta, meta)', value_format='percent', color_mode='threshold', threshold='1',
             subtitle='{venta} de {meta} · rojo si es menor al 100 %', color='#F0FDF4'),
        dict(type='kpi', name='Meta de venta', code='meta', width='3', model=GOAL, since='19.0.8.0.0', sequence=14,
             map={'periodo': 'date'}, measures=[m('Meta', 'meta', 'sum', 'amount')], value_format='monetary',
             subtitle='Σ metas mensuales del periodo (de la empresa)', color='#EFF6FF'),
        dict(type='kpi', name='Pipeline enviado', code='pipeline', width='3', model='crm.lead', domain=d(*PIPE_D),
             map={'periodo': None}, sequence=16, measures=[m('Pipeline', 'pipeline', 'sum', REVENUE)],
             value_format='monetary', color='#FFF7ED',
             subtitle='{pipeline_n} cotizaciones · {env_180} con más de 180 días ({env_180_monto})'),
        # Renglón 2
        dict(type='kpi', name='Ganados', code='ganados', width='3', model='crm.lead', domain=d(*WON_C),
             map={'periodo': 'date_closed'}, sequence=20, measures=[m('Ganados', 'ganados')], value_format='integer',
             abbreviate=False, subtitle='cotizaciones ganadas · SR {ganados_sr} · R {ganados_r}', color='#EFF6FF'),
        dict(type='kpi', name='Perdidos', code='perdidos', width='3', model='crm.lead', domain=d(*LOST_C),
             map={'periodo': 'date_closed'}, sequence=22, measures=[m('Perdidos', 'perdidos')],
             value_format='integer', abbreviate=False,
             subtitle='cotizaciones perdidas · SR {perdidos_sr} · R {perdidos_r}', color='#FEF2F2'),
        dict(type='kpi', name='Efectividad de cierre', code='efectividad', width='3', sequence=24,
             formula='div(ganados, ganados + perdidos)', value_format='percent',
             subtitle='ganados / (ganados + perdidos) · SR {efectividad_sr} · R {efectividad_r}', color='#F0FDF4'),
        dict(type='kpi', name='Semana (últimos 7 días)', code='venta_7d', width='3', model='crm.lead',
             domain=d(*(SALE_D + (_since(7, 'date_closed'),))), map={'periodo': None}, since=V10, sequence=26,
             measures=[m('Venta', 'venta_7d', 'sum', REVENUE)], value_format='monetary', color='#F9FAFB',
             subtitle='{ganados_7d} ganados · {perdidos_7d} perdidos por {perdidos_7d_monto} · '
                      '{leads_7d} leads nuevos'),
        # Renglón 3
        dict(type='kpi', name='Invitaciones a cotizar', code='invitaciones', width='3', model='crm.lead',
             domain=d(*INV_C), sequence=30, measures=[m('Invitaciones', 'invitaciones')],
             value_format='integer', abbreviate=False, subtitle='cotizadas + declinadas', color='#F9FAFB'),
        dict(type='kpi', name='Atendidas (cotizadas)', code='atendidas', width='3', model='crm.lead',
             domain=d(*ATT_C), sequence=32, measures=[m('Atendidas', 'atendidas')],
             value_format='integer', abbreviate=False,
             subtitle='por fecha de creación · {atendidas_pct} de las invitaciones', color='#F9FAFB'),
        dict(type='kpi', name='% de bateo', code='bateo', width='3', sequence=34, formula='div(ganados, atendidas)',
             value_format='percent', subtitle='SR {bateo_sr} · R {bateo_r} · base hist. {bateo_hist}',
             color='#F0FDF4'),
        dict(type='kpi', name='Semanas creación→cierre', code='semanas', width='3', model='crm.lead',
             domain=d(*SALE_D), map={'periodo': 'date_closed'}, since=V10, sequence=36,
             measures=[m('Semanas', 'semanas', 'avg', 'report_close_weeks')], value_format='number1',
             abbreviate=False, subtitle='promedio de ganados · SR {semanas_sr} · R {semanas_r}', color='#F9FAFB'),
        # Ocultos (para notas y fórmulas)
        hk('Venta SR (cierre)', 'venta_sr', SALE_D + (SR,), 'date_closed', 50, 'sum', REVENUE, 'monetary'),
        hk('Venta R (cierre)', 'venta_r', SALE_D + (R,), 'date_closed', 51, 'sum', REVENUE, 'monetary'),
        hk('Ganados SR', 'ganados_sr', WON_C + (SR,), 'date_closed', 52),
        hk('Ganados R', 'ganados_r', WON_C + (R,), 'date_closed', 53),
        hk('Perdidos SR', 'perdidos_sr', LOST_C + (SR,), 'date_closed', 54),
        hk('Perdidos R', 'perdidos_r', LOST_C + (R,), 'date_closed', 55),
        hk('Efectividad SR', 'efectividad_sr', sequence=56, value_format='percent',
           formula='div(ganados_sr, ganados_sr + perdidos_sr)'),
        hk('Efectividad R', 'efectividad_r', sequence=57, value_format='percent',
           formula='div(ganados_r, ganados_r + perdidos_r)'),
        hk('Atendidas SR', 'atendidas_sr', ATT_C + (SR,), sequence=58),
        hk('Atendidas R', 'atendidas_r', ATT_C + (R,), sequence=59),
        hk('Bateo SR', 'bateo_sr', sequence=60, value_format='percent', formula='div(ganados_sr, atendidas_sr)'),
        hk('Bateo R', 'bateo_r', sequence=61, value_format='percent', formula='div(ganados_r, atendidas_r)'),
        hk('Atendidas %', 'atendidas_pct', sequence=62, value_format='percent', formula='div(atendidas, invitaciones)'),
        hk('Ganados (histórico)', 'ganados_hist', WON_C, None, 63),
        hk('Ganados SR (histórico)', 'ganados_hist_sr', WON_C + (SR,), None, 64),
        hk('Ganados R (histórico)', 'ganados_hist_r', WON_C + (R,), None, 65),
        hk('Atendidas SR (histórico)', 'atendidas_hist_sr', ATT_C + (SR,), None, 66),
        hk('Atendidas R (histórico)', 'atendidas_hist_r', ATT_C + (R,), None, 67),
        hk('Bateo histórico SR', 'bateo_hist_sr', sequence=68, value_format='percent',
           formula='div(ganados_hist_sr, atendidas_hist_sr)'),
        hk('Bateo histórico R', 'bateo_hist_r', sequence=69, value_format='percent',
           formula='div(ganados_hist_r, atendidas_hist_r)'),
        hk('Cotizaciones enviadas', 'pipeline_n', PIPE_D, None, 70),
        hk('Enviadas > 180 días', 'env_180', PIPE_D + (_since(180, 'create_date').replace('>=', '<'),), None, 71),
        hk('Enviadas > 180 días (monto)', 'env_180_monto', PIPE_D + (_since(180, 'create_date').replace('>=', '<'),),
           None, 72, 'sum', REVENUE, 'monetary'),
        hk('Ganados 7 días', 'ganados_7d', WON_C + (_since(7, 'date_closed'),), None, 73),
        hk('Perdidos 7 días', 'perdidos_7d', LOST_C + (_since(7, 'date_closed'),), None, 74),
        hk('Perdidos 7 días (monto)', 'perdidos_7d_monto', LOST_C + (_since(7, 'date_closed'),), None, 75, 'sum',
           REVENUE, 'monetary'),
        hk('Leads nuevos 7 días', 'leads_7d', (ARCHIVED, _since(7, 'create_date')), None, 76),
        hk('Semanas SR', 'semanas_sr', SALE_D + (SR,), 'date_closed', 77, 'avg', 'report_close_weeks', 'number1'),
        hk('Semanas R', 'semanas_r', SALE_D + (R,), 'date_closed', 78, 'avg', 'report_close_weeks', 'number1'),
        hk('Ticket SR', 'ticket_sr', sequence=79, value_format='monetary', formula='div(venta_sr, ganados_sr)'),
        hk('Ticket R', 'ticket_r', sequence=80, value_format='monetary', formula='div(venta_r, ganados_r)'),
        hk('Venta SR %', 'venta_sr_pct', sequence=81, value_format='percent', formula='div(venta_sr, venta)'),
        hk('Venta R %', 'venta_r_pct', sequence=82, value_format='percent', formula='div(venta_r, venta)'),
        hk('Ingenierías (proyectos)', 'ing_n', SALE_D + ("('name', 'ilike', 'ingenier')",), 'date_closed', 83),
        hk('Ingenierías %', 'ing_pct', sequence=84, value_format='percent', formula='div(ing_monto, venta)'),
        hk('Invitaciones (histórico)', 'inv_hist', INV_C, None, 85),
        hk('Cotizados % (histórico)', 'cot_hist_pct', sequence=86, value_format='percent',
           formula='div(atendidas_hist, inv_hist)'),
        hk('Declinados % (histórico)', 'decl_hist_pct', sequence=87, value_format='percent',
           formula='div(declinados_hist, inv_hist)'),
        hk('Invitaciones trimestre anterior', 'inv_prev_q', INV_C + LAST_QUARTER, None, 88),
        hk('Cotizados SR trimestre', 'cot_sr_q', ATT_C + (SR, THIS_QUARTER), None, 89),
        hk('Cotizados R trimestre', 'cot_r_q', ATT_C + (R, THIS_QUARTER), None, 90),
        hk('Declinados trimestre', 'decl_q', INV_C + (DECLINED, THIS_QUARTER), None, 91),
        # ================= 1–2. Invitaciones a cotizar =================
        dict(type='section', name='Invitaciones a cotizar', sequence=95),
        dict(type='chart', name='Invitaciones a cotizar por mes', width='6', model='crm.lead', domain=d(*INV_C),
             groupby='create_date', interval='month', groupby2='report_invitation_status', chart_type='bar_stacked',
             show_values=True, sequence=100, measures=[m('Invitaciones', 'invitaciones')]),
        dict(type='chart', name='Histórico de invitaciones por trimestre', width='6', model='crm.lead',
             domain=d(*INV_C), groupby='create_date', interval='quarter', groupby2='report_invitation_status',
             chart_type='bar_stacked', map={'periodo': None}, show_values=True, sequence=110,
             subtitle='todos los años · {inv_hist} invitaciones', measures=[m('Invitaciones', 'invitaciones')]),
        dict(type='kpi', name='Cotizados (histórico)', code='atendidas_hist', width='3', model='crm.lead',
             domain=d(*ATT_C), map={'periodo': None}, since=V10, sequence=111,
             measures=[m('Cotizados', 'atendidas_hist')], value_format='integer', abbreviate=False,
             subtitle='{cot_hist_pct} de las invitaciones, todos los años', color='#F9FAFB'),
        dict(type='kpi', name='Declinados (histórico)', code='declinados_hist', width='3', model='crm.lead',
             domain=d(*(INV_C + (DECLINED,))), map={'periodo': None}, since=V10, sequence=112,
             measures=[m('Declinados', 'declinados_hist')], value_format='integer', abbreviate=False,
             subtitle='{decl_hist_pct} de las invitaciones, todos los años', color='#F9FAFB'),
        dict(type='kpi', name='% de bateo histórico', code='bateo_hist', width='3', since=V10, sequence=113,
             formula='div(ganados_hist, atendidas_hist)', value_format='percent',
             subtitle='base congelada · SR {bateo_hist_sr} · R {bateo_hist_r}', color='#F0FDF4'),
        dict(type='kpi', name='Trimestre en curso', code='inv_q', width='3', model='crm.lead',
             domain=d(*(INV_C + (THIS_QUARTER,))), map={'periodo': None}, since=V10, sequence=114,
             measures=[m('Invitaciones', 'inv_q')], value_format='integer', abbreviate=False, color='#F9FAFB',
             subtitle='invitaciones · vs {inv_prev_q} el trimestre anterior · SR cotizados {cot_sr_q} · '
                      'R cotizados {cot_r_q} · declinados {decl_q}'),
        dict(type='table', name='Invitaciones a cotizar, mes a mes', width='12', model='crm.lead',
             since='19.0.8.0.0', sequence=118, domain=d(*INV_C), groupby='create_date',
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
                 m('No atendidos', 'na', value_format='integer', extra_domain='[%s]' % DECLINED),
                 m('% no atendidos', 'na_pct', formula='div(na, invitaciones)', value_format='percent'),
             ]),
        # ================= 3–4. Ganados, perdidos y venta =================
        dict(type='section', name='Ganados, perdidos y venta', sequence=120),
        dict(type='chart', name='Ganados y perdidos por mes de cierre', width='6', model='crm.lead',
             domain=d(OPP, ARCHIVED, "('report_close_status', '!=', False)"), groupby='date_closed',
             interval='month', groupby2='report_close_status', chart_type='bar_stacked', show_values=True,
             map={'periodo': 'date_closed'}, sequence=130, height=420,
             measures=[m('Cotizaciones', 'cotizaciones')]),
        dict(type='table', name='Embudo: Totales, Sin Recompra y Recompra', width='6', model='crm.lead',
             domain=d(OPP, ARCHIVED), groupby='report_segment_group', table_transpose=True, total_first=True,
             since=V10, sequence=132, height=420,
             subtitle='Invitaciones, atendidos y declinados por fecha de creación; ganados y perdidos por fecha '
                      'de cierre. Clic en un número para ver las oportunidades.',
             measures=[
                 m('Invitaciones a cotizar', 'invitaciones', extra_domain=d(INVITATIONS), value_format='integer'),
                 m('Atendidos (cotizados)', 'atendidos', extra_domain=d(ATTENDED), value_format='integer'),
                 m('% de las invitaciones', 'atendidos_pct', formula='div(atendidos, invitaciones)',
                   value_format='percent'),
                 m('Declinados', 'declinados', extra_domain=d(DECLINED), value_format='integer'),
                 m('% de las invitaciones', 'declinados_pct', formula='div(declinados, invitaciones)',
                   value_format='percent'),
                 m('Ganados', 'ganados', extra_domain=d(WON), period_field='date_closed', value_format='integer'),
                 m('% de los atendidos', 'ganados_pct', formula='div(ganados, atendidos)', value_format='percent'),
                 m('Perdidos', 'perdidos', extra_domain=d(LOST), period_field='date_closed', value_format='integer'),
                 m('% de los atendidos', 'perdidos_pct', formula='div(perdidos, atendidos)', value_format='percent'),
                 m('Pendientes de respuesta', 'pendientes', formula='atendidos - ganados - perdidos',
                   value_format='integer'),
                 m('% de los atendidos', 'pendientes_pct', formula='div(pendientes, atendidos)',
                   value_format='percent'),
                 m('% de bateo (G / atendidos)', 'bateo', formula='div(ganados, atendidos)', value_format='percent'),
                 m('Efectividad de cierre (G / G+P)', 'efectividad', formula='div(ganados, ganados + perdidos)',
                   value_format='percent'),
                 m('Ganados (histórico)', 'ganados_h', extra_domain=d(WON), ignore_period=True, hidden=True),
                 m('Atendidos (histórico)', 'atendidos_h', extra_domain=d(ATTENDED), ignore_period=True, hidden=True),
                 m('% bateo histórico (base)', 'bateo_h', formula='div(ganados_h, atendidos_h)',
                   value_format='percent'),
             ]),
        dict(type='kpi', name='Venta Sin Recompra', code='venta_sr_v', width='3', since=V10, sequence=134,
             formula='venta_sr', value_format='monetary', color='#EFF6FF',
             subtitle='{ganados_sr} proyectos · {venta_sr_pct} · ticket {ticket_sr}'),
        dict(type='kpi', name='Venta Recompra', code='venta_r_v', width='3', since=V10, sequence=135,
             formula='venta_r', value_format='monetary', color='#EFF6FF',
             subtitle='{ganados_r} proyectos · {venta_r_pct} · ticket {ticket_r}'),
        dict(type='kpi', name='Ticket promedio', code='ticket', width='3', since=V10, sequence=136,
             formula='div(venta, ganados)', value_format='monetary', color='#F9FAFB',
             subtitle='venta ganada / {ganados} proyectos'),
        dict(type='kpi', name='Ingenierías', code='ing_monto', width='3', model='crm.lead',
             domain=d(*(SALE_D + ("('name', 'ilike', 'ingenier')",))), map={'periodo': 'date_closed'}, since=V10,
             sequence=137, measures=[m('Ingenierías', 'ing_monto', 'sum', REVENUE)], value_format='monetary',
             subtitle='{ing_n} proyectos · {ing_pct} de la venta (nombre contiene "ingenier")', color='#F9FAFB'),
        dict(type='chart', name='Venta por mes de cierre', width='6', model='crm.lead', domain=d(*SALE_D),
             groupby='date_closed', interval='month', groupby2='report_segment', chart_type='bar_stacked',
             map={'periodo': 'date_closed'}, show_values=True, sequence=140,
             measures=[m('Venta', 'venta', 'sum', REVENUE, value_format='monetary')]),
        dict(type='chart', name='Venta por trimestre vs meta acumulada', width='6', model='crm.lead',
             domain=d(*SALE_D), groupby='date_closed', interval='quarter', chart_type='bar',
             map={'periodo': 'date_closed'}, show_values=True, since=V10, sequence=142,
             subtitle='La meta se captura en CRM › Configuración › Metas de venta mensuales.', measures=[
                 m('Venta del trimestre', 'venta', 'sum', REVENUE, value_format='monetary', color='#2F5BEA'),
                 m('Acumulado', 'acumulado', 'sum', REVENUE, value_format='monetary', color=CUMULATIVE_COLOR,
                   cumulative=True),
                 m('Meta acumulada', 'meta', 'sum', 'amount', source_model=GOAL, source_groupby_field='date',
                   value_format='monetary', color='#F28C28', cumulative=True),
             ]),
        dict(type='chart', name='Venta por mes de cierre vs meta mensual', width='12', model='crm.lead',
             since='19.0.8.0.0', sequence=144, domain=d(*SALE_D),
             groupby='date_closed', interval='month', chart_type='bar', map={'periodo': 'date_closed'},
             subtitle='La meta se captura en CRM › Configuración › Metas de venta mensuales.', measures=[
                 m('Venta ganada', 'venta', 'sum', REVENUE, value_format='monetary', color='#2F5BEA'),
                 m('Meta mensual', 'meta', 'sum', 'amount', source_model=GOAL, source_groupby_field='date',
                   value_format='monetary', color='#F59E0B', series_type='line'),
             ]),
        dict(type='chart', name='Razones de pérdida', width='6', model='crm.lead',
             domain=d(OPP, "('active', '=', False)", "('won_status', '=', 'lost')"), groupby='lost_reason_id',
             chart_type='hbar', sort_mode='value_desc', map={'periodo': 'date_closed'}, show_legend=False,
             show_values=True, sequence=150, measures=[m('Perdidos', 'perdidos')]),
        dict(type='chart', name='Prospección Sin recompra por etapa', width='6', model='crm.lead',
             domain=d(*PROSPECTING_D), groupby='create_date', interval='month', groupby2='stage_id',
             chart_type='bar_stacked', show_values=True, sequence=160,
             subtitle='por mes de creación', measures=[m('Oportunidades', 'oportunidades')]),
        # ================= 10. Origen de leads Sin Recompra =================
        dict(type='section', name='Origen de leads Sin Recompra', since=V10, sequence=170, requires=ORIGIN,
             subtitle='¿Cómo se generó el lead? · leads creados en el periodo, invitaciones cotizadas y ganados'),
        dict(type='chart', name='Leads Sin Recompra por canal de origen', width='6', model='crm.lead',
             domain=ORIGIN_DOMAIN, groupby=ORIGIN,
             chart_type='hbar', sort_mode='value_desc', show_values=True, since=V10, sequence=172, height=380,
             requires=ORIGIN, measures=[
                 m('Leads', 'leads', color='#C9CED8'),
                 m('Cotizados', 'cotizados', extra_domain=d(ATTENDED), color='#8DA8F0'),
                 m('Ganados', 'ganados', extra_domain="[('won_status', '=', 'won')]", color='#2F5BEA'),
             ]),
        dict(type='table', name='Origen de leads Sin Recompra (tabla)', width='6', model='crm.lead',
             domain=ORIGIN_DOMAIN, groupby=ORIGIN,
             sort_mode='value_desc', row_label='Origen', since=V10, sequence=174, height=380, requires=ORIGIN,
             subtitle='% cot. = cotizados / leads · % gan. = ganados / cotizados', measures=[
                 m('Leads', 'leads', value_format='integer'),
                 m('Cotizados', 'cotizados', extra_domain=d(ATTENDED), value_format='integer'),
                 m('Ganados', 'ganados', extra_domain="[('won_status', '=', 'won')]", value_format='integer'),
                 m('% cot.', 'pct_cot', formula='div(cotizados, leads)', value_format='percent'),
                 m('% gan.', 'pct_gan', formula='div(ganados, cotizados)', value_format='percent'),
             ]),
        # ================= Pipeline abierto por antigüedad (19.0.8.0.0) =================
        dict(type='section', name='Pipeline abierto por antigüedad', since='19.0.8.0.0', sequence=190),
        dict(type='chart', name='Antigüedad del pipeline enviado', width='6', model='crm.lead',
             since='19.0.8.0.0', sequence=200, domain=d(*PIPE_D), range_field='create_date',
             range_bounds='30,60,90,180', chart_type='bar', map={'periodo': None}, show_values=True,
             subtitle='días desde la creación, hoy; barras = oportunidades, línea = monto', measures=[
                 m('Oportunidades', 'oportunidades', value_format='integer', color='#2F5BEA'),
                 m('Monto', 'monto', 'sum', REVENUE, value_format='monetary', color='#F59E0B',
                   series_type='line', right_axis=True),
             ]),
        dict(type='table', name='Pipeline enviado por rango de días', width='6', model='crm.lead',
             since='19.0.8.0.0', sequence=210, domain=d(*PIPE_D), range_field='create_date',
             range_bounds='30,60,90,180', row_label='Días desde la creación', map={'periodo': None},
             measures=[
                 m('Oportunidades', 'oportunidades', value_format='integer'),
                 m('Monto', 'monto', 'sum', REVENUE, value_format='monetary'),
                 m('% del monto', 'pct', formula='div(monto, pipeline)', value_format='percent'),
             ]),
    ],
}

# Notas de fábrica anteriores: la migración 19.0.10.0.0 solo cambia la nota de
# un elemento si todavía tiene la de fábrica (no pisa cambios del usuario).
OLD_COMMERCIAL_SUBTITLES = {
    'Venta ganada': 'por fecha de cierre',
    'Ganados': 'cotizaciones ganadas',
    'Perdidos': 'cotizaciones perdidas',
    'Efectividad de cierre': 'ganados / (ganados + perdidos)',
    'Atendidas (cotizadas)': 'por fecha de creación',
    '% de bateo': 'ganados / atendidas',
    'Pipeline enviado': 'pendiente de respuesta, hoy',
    'Avance vs meta': 'venta ganada / meta; rojo si es menor al 100 %',
    'Histórico de invitaciones por trimestre': 'todos los años',
}
# Reemplazados por la tabla "Embudo: Totales, Sin Recompra y Recompra"
OLD_COMMERCIAL_NAMES = ['Embudo por segmento', 'Embudo por segmento (periodo seleccionado)']


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
V12 = '19.0.12.0.0'
WEEK_REPORT = {
    'xmlid': 'dashboard_week_report',
    'name': 'Reporte semanal Dirección',
    'category': 'Dirección',
    'sequence': 30,
    'groups': ['project.group_project_user'],
    'description': 'Proyectos en curso. Por omisión muestra la semana vigente (la última cerrada); elige otra '
                   'semana en el filtro. Elige uno o varios proyectos para ver solo esos (gráficas por '
                   'proyecto, costos por partida y margen semanal). Rojo en el margen = menor a la alerta '
                   'de la semana; verde / rojo en desviaciones = optimización / sobrecosto.',
    'filters': [
        dict(key='semana', name='Semana', filter_type='many2one', field_name='week_id',
             comodel='business.report.week', multiple=False, required=True,
             default_domain="[('is_current', '=', True)]"),
        dict(key='proyecto', name='Proyecto', filter_type='many2one', field_name='analytic_account_id',
             comodel='account.analytic.account', multiple=True),
    ],
    'widgets': [
        dict(type='section', name='Resumen de Dirección', sequence=5, since=V12,
             subtitle='Σ proyectos en análisis de la semana elegida'),
        # ---------------- Indicadores ----------------
        dict(type='kpi', sequence=10, name='Costo planeado', code='planeado', width='3', model=PARTIDA,
             measures=[m('Planeado', 'planeado', 'sum', 'planned_amount')], value_format='monetary',
             subtitle='NeoData, Σ partidas', color='#EFF6FF'),
        dict(type='kpi', sequence=20, name='Costo real', code='real', width='3', model=PARTIDA,
             measures=[m('Real', 'real', 'sum', 'real_amount')], value_format='monetary',
             subtitle='Odoo, a la fecha de corte', color='#F9FAFB'),
        dict(type='kpi', sequence=30, name='Desviación acumulada', code='desviacion', width='3', formula='planeado - real',
             value_format='monetary', color_mode='sign', subtitle='planeado − real', color='#F0FDF4'),
        dict(type='kpi', sequence=40, name='% de optimización', code='optimizacion', width='3',
             formula='div(desviacion, planeado)', value_format='percent', color_mode='sign',
             subtitle='desviación / planeado', color='#F0FDF4'),
        dict(type='kpi', sequence=50, name='Δ planeado', code='delta_planeado', hidden=True, model=PARTIDA,
             measures=[m('Δ planeado', 'delta_planeado', 'sum', 'planned_delta')]),
        dict(type='kpi', sequence=60, name='Δ real', code='delta_real', hidden=True, model=PARTIDA,
             measures=[m('Δ real', 'delta_real', 'sum', 'real_delta')]),
        dict(type='kpi', sequence=70, name='Desviación vs semana anterior', code='delta_desviacion', width='3',
             formula='delta_planeado - delta_real', value_format='monetary', color_mode='sign',
             subtitle='cambio de la desviación', color='#F0FDF4'),
        dict(type='kpi', sequence=80, name='Venta semanal', code='venta_semanal', width='3', model=PROJECT,
             measures=[m('Venta semanal', 'venta_semanal', 'sum', 'neodata_advance')], value_format='monetary',
             subtitle='Σ avance NeoData', color='#FFF7ED'),
        dict(type='kpi', sequence=90, name='Venta real', code='venta_real', hidden=True, model=PROJECT,
             measures=[m('Venta real', 'venta_real', 'sum', 'estimate_amount')]),
        dict(type='kpi', sequence=100, name='Costo real proyectos', code='costo_proyectos', hidden=True, model=PROJECT,
             measures=[m('Costo', 'costo_proyectos', 'sum', 'real_total')]),
        dict(type='kpi', sequence=110, name='Alerta de margen', code='alerta', hidden=True, model='business.report.week',
             map={'semana': 'id', 'proyecto': None},
             measures=[m('Alerta', 'alerta', 'max', 'margin_alert_pct')]),
        dict(type='kpi', sequence=120, name='Margen operativo', code='margen', width='3', formula='venta_real - costo_proyectos',
             value_format='monetary', color_mode='sign', subtitle='estimado autorizado − costo real',
             color='#F0FDF4'),
        dict(type='kpi', sequence=130, name='% margen operativo', code='margen_pct', width='3',
             formula='div(margen, venta_real)', value_format='percent', color_mode='threshold', threshold='alerta',
             subtitle='rojo si es menor a la alerta de la semana', color='#F0FDF4'),
        # ---------------- Resumen: gráficas y tablas ----------------
        dict(type='chart', name='Balance de costos por partida', sequence=140, width='4', model=PARTIDA,
             groupby='partida', chart_type='bar', subtitle='Σ planeado vs Σ real por posición', measures=[
                 m('Planeado (NeoData)', 'planeado', 'sum', 'planned_amount', color='#2F5BEA', value_format='monetary'),
                 m('Real (Odoo)', 'real', 'sum', 'real_amount', color='#E8556F', value_format='monetary')]),
        dict(type='table', name='Margen operativo al momento – proyectos', sequence=170, width='12', model=PROJECT,
             groupby='analytic_account_id', row_label='Proyecto', total_first=True,
             drilldown_view='custom_business_reports.business_report_week_project_view_form_detail',
             measures=[
                 m('Venta real', 'venta', 'sum', 'estimate_amount', value_format='monetary'),
                 m('Costo real', 'costo', 'sum', 'real_total', value_format='monetary'),
                 m('Margen operativo', 'margen', formula='venta - costo', value_format='monetary'),
                 m('% margen', 'pct', formula='div(margen, venta)', value_format='percent',
                   color_mode='threshold', threshold='alerta')]),
        # Láminas "Indicadores costos y venta": desviación acumulada (verde / rojo) y venta semanal
        dict(type='chart', name='Indicador de costos: desviación acumulada por semana', sequence=145, width='4',
             model=PROJECT, groupby='week_date', interval='day', chart_type='bar', map={'semana': None},
             since=V12, subtitle='planeado − real de los proyectos, todas las semanas · verde = optimización',
             show_legend=False, show_values=True, measures=[
                 m('Desviación acumulada', 'desviacion', 'sum', 'deviation', value_format='monetary',
                   color_mode='sign')]),
        dict(type='chart', name='Indicador de venta semanal', sequence=150, width='4', model=PROJECT,
             groupby='week_date', interval='day', chart_type='bar', map={'semana': None}, since=V12,
             subtitle='Σ avance semanal NeoData, todas las semanas', show_legend=False, show_values=True,
             measures=[m('Venta semanal (avance NeoData)', 'venta', 'sum', 'neodata_advance', color='#F59E0B',
                         value_format='monetary')]),
        dict(type='table', name='Balance de costos por partida (Σ proyectos en análisis)', sequence=160, width='12',
             model=PARTIDA, groupby='partida', row_label='Partida', measures=[
                 m('Planeado', 'planeado', 'sum', 'planned_amount', value_format='monetary'),
                 m('Real', 'real', 'sum', 'real_amount', value_format='monetary'),
                 m('Diferencia', 'diferencia', formula='planeado - real', value_format='monetary', color_mode='sign'),
                 m('%', 'pct', formula='div(diferencia, planeado)', value_format='percent', color_mode='sign'),
                 m('Δ planeado vs sem. ant.', 'delta_planeado', 'sum', 'planned_delta', value_format='monetary'),
                 m('Δ real vs sem. ant.', 'delta_real', 'sum', 'real_delta', value_format='monetary')]),

        # ---------------- Por proyecto (lámina "Costos" y "Balance financiero") ----------------
        dict(type='section', name='Por proyecto (cuenta analítica)', sequence=200, since=V12,
             subtitle='Un grupo por proyecto; filtra un proyecto para ver solo el suyo'),
        dict(type='chart', name='Desviación por cuenta analítica', sequence=210, width='6', model=PROJECT,
             groupby='analytic_account_id', chart_type='bar', since=V12, sort_mode='value_desc',
             subtitle='costo planeado − costo real · verde = optimización, rojo = sobrecosto',
             show_legend=False, show_values=True, measures=[
                 m('Desviación', 'desviacion', 'sum', 'deviation', value_format='monetary', color_mode='sign')]),
        dict(type='table', name='Desviación por cuenta analítica (tabla)', sequence=215, width='12', model=PROJECT,
             groupby='analytic_account_id', row_label='Proyecto', total_first=True, since=V12,
             drilldown_view='custom_business_reports.business_report_week_project_view_form_detail',
             measures=[
                 m('Planeado', 'planeado', 'sum', 'planned_total', value_format='monetary'),
                 m('Real', 'real', 'sum', 'real_total', value_format='monetary'),
                 m('Desviación', 'desviacion', formula='planeado - real', value_format='monetary', color_mode='sign'),
                 m('%', 'pct', formula='div(desviacion, planeado)', value_format='percent', color_mode='sign')]),
        dict(type='chart', name='Costos por proyecto: planeado vs real', sequence=212, width='6', model=PROJECT,
             groupby='analytic_account_id', chart_type='bar', since=V12,
             subtitle='Σ partidas de cada proyecto', measures=[
                 m('Planeado (NeoData)', 'planeado', 'sum', 'planned_total', color='#2F5BEA', value_format='monetary'),
                 m('Real (Odoo)', 'real', 'sum', 'real_total', color='#E8556F', value_format='monetary')]),
        dict(type='chart', name='Costo real por proyecto y partida', sequence=225, width='6', model=PARTIDA,
             groupby='analytic_account_id', groupby2='partida', chart_type='bar_stacked', since=V12,
             subtitle='EyH, indirectos, mano de obra, materiales y subcontratistas', measures=[
                 m('Real (Odoo)', 'real', 'sum', 'real_amount', value_format='monetary')]),
        dict(type='chart', name='Margen operativo NeoData por proyecto', sequence=230, width='6', model=PROJECT,
             groupby='analytic_account_id', chart_type='bar', since=V12,
             subtitle='venta reconocida NeoData − costo real', measures=[
                 m('Venta reconocida NeoData', 'venta', 'sum', 'neodata_sale', color='#E07A1F',
                   value_format='monetary'),
                 m('Costo real', 'costo', 'sum', 'real_total', color='#E8556F', value_format='monetary'),
                 m('Margen NeoData', 'margen', 'sum', 'neodata_margin', color='#93C5FD', value_format='monetary')]),
        dict(type='chart', name='Margen operativo NeoData por semana', sequence=245, width='6', model=PROJECT,
             groupby='week_date', interval='day', chart_type='bar', map={'semana': None}, since=V12,
             subtitle='histórico de los proyectos elegidos (o de todos)', show_legend=False, show_values=True,
             measures=[m('Margen NeoData', 'margen', 'sum', 'neodata_margin', value_format='monetary',
                         color_mode='sign')]),
        dict(type='chart', name='Balance financiero por proyecto', sequence=240, width='12', model=PROJECT,
             groupby='analytic_account_id', chart_type='hbar', since=V12,
             subtitle='estimado autorizado = Ventas sin anticipos · restante = contrato − estimado autorizado',
             height=360, measures=[
                 m('Valor contrato', 'contrato', 'sum', 'contract_amount', color='#15803D', value_format='monetary'),
                 m('Venta NeoData', 'neodata', 'sum', 'neodata_sale', color='#E07A1F', value_format='monetary'),
                 m('Estimado autorizado', 'estimado', 'sum', 'estimate_amount', color='#2F5BEA',
                   value_format='monetary'),
                 m('Restante por estimar', 'restante', 'sum', 'remaining_estimate', color='#EAB308',
                   value_format='monetary'),
                 m('Facturado', 'facturado', 'sum', 'invoiced_amount', color='#A8A29E', value_format='monetary'),
                 m('OC en revisión', 'oc', 'sum', 'oc_review', color='#9CA3AF', value_format='monetary'),
                 m('Estimación en revisión', 'est_rev', 'sum', 'estimate_review', color='#D1D5DB',
                   value_format='monetary')]),
        dict(type='chart', name='Costo planeado vs real por semana', sequence=250, width='6', model=PROJECT,
             groupby='week_date', interval='day', chart_type='line', map={'semana': None}, since=V12,
             subtitle='histórico de los proyectos elegidos (o de todos)', measures=[
                 m('Planeado (NeoData)', 'planeado', 'sum', 'planned_total', color='#2F5BEA', value_format='monetary'),
                 m('Real (Odoo)', 'real', 'sum', 'real_total', color='#E8556F', value_format='monetary')]),

        # ---------------- Semana (lámina "Costos 2") ----------------
        dict(type='section', name='Semana: margen semanal y diferencia de costos', sequence=300, since=V12,
             subtitle='Avance NeoData vs costo de la semana; Δ de cada partida vs la semana anterior'),
        dict(type='table', name='Margen semanal por proyecto', sequence=310, width='12', model=PROJECT,
             groupby='analytic_account_id', row_label='Proyecto', total_first=True, since=V12,
             drilldown_view='custom_business_reports.business_report_week_project_view_form_detail',
             measures=[
                 m('Venta NeoData sem. actual', 'venta', 'sum', 'neodata_sale', value_format='monetary'),
                 m('Venta NeoData sem. anterior', 'venta_ant', 'sum', 'neodata_sale_prev', value_format='monetary'),
                 m('Avance semanal NeoData', 'avance', 'sum', 'neodata_advance', value_format='monetary'),
                 m('Costo de la semana', 'costo', 'sum', 'week_cost', value_format='monetary'),
                 m('Diferencia', 'diferencia', 'sum', 'week_difference', value_format='monetary',
                   color_mode='sign')]),
        dict(type='chart', name='Margen semanal por semana', sequence=320, width='6', model=PROJECT,
             groupby='week_date', interval='day', chart_type='bar', map={'semana': None}, since=V12,
             subtitle='avance NeoData vs costo de la semana, todas las semanas', measures=[
                 m('Avance semanal NeoData', 'avance', 'sum', 'neodata_advance', color='#F59E0B',
                   value_format='monetary'),
                 m('Costo de la semana', 'costo', 'sum', 'week_cost', color='#E8556F', value_format='monetary'),
                 m('Diferencia', 'diferencia', 'sum', 'week_difference', color='#10B981', value_format='monetary',
                   series_type='line')]),
        dict(type='chart', name='Diferencia de costos semanal por partida', sequence=330, width='6', model=PARTIDA,
             groupby='partida', chart_type='bar', since=V12,
             subtitle='Δ planeado y Δ real vs la semana anterior · diferencia = Δ planeado − Δ real', measures=[
                 m('Δ planeado', 'delta_planeado', 'sum', 'planned_delta', color='#2F5BEA', value_format='monetary'),
                 m('Δ real', 'delta_real', 'sum', 'real_delta', color='#93C5FD', value_format='monetary'),
                 m('Diferencia', 'diferencia', 'sum', 'week_difference', value_format='monetary',
                   color_mode='sign')]),
        dict(type='table', name='Diferencia de costos semanal por partida (tabla)', sequence=335, width='12',
             model=PARTIDA, groupby='partida', row_label='Partida', since=V12, measures=[
                 m('Planeado sem. anterior', 'planeado_ant', 'sum', 'planned_prev', value_format='monetary'),
                 m('Planeado sem. actual', 'planeado', 'sum', 'planned_amount', value_format='monetary'),
                 m('Δ planeado', 'delta_planeado', 'sum', 'planned_delta', value_format='monetary'),
                 m('Real sem. anterior', 'real_ant', 'sum', 'real_prev', value_format='monetary'),
                 m('Real sem. actual', 'real', 'sum', 'real_amount', value_format='monetary'),
                 m('Δ real', 'delta_real', 'sum', 'real_delta', value_format='monetary'),
                 m('Diferencia', 'diferencia', formula='delta_planeado - delta_real', value_format='monetary',
                   color_mode='sign')]),

        # ---------------- Detalle ----------------
        dict(type='list', name='Proyectos en análisis', sequence=400, width='12', model=PROJECT, limit=30,
             drilldown_view='custom_business_reports.business_report_week_project_view_form_detail',
             list_fields='analytic_account_id, contract_amount, estimate_amount, invoiced_amount, neodata_sale, '
                         'planned_total, real_total, deviation, operating_margin',
             list_order='sequence, id'),
    ],
}

# 19.0.12.0.0: el combinado "Indicadores de costos y venta por semana" se separa
# en las dos gráficas de la lámina (indicador de costos e indicador de venta).
OLD_WEEK_NAMES = ['Indicadores de costos y venta por semana']

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
        if _available(env, item):
            _create_widget(env, dashboard, filters, item, item.get('sequence', seq))
    return dashboard


def _available(env, item):
    """Los elementos con 'requires' (p. ej. un campo de Studio) solo se crean si el campo existe."""
    return not item.get('requires') or item['requires'] in env[item.get('model') or 'crm.lead']._fields


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
            if not item.get('since') or (since and item['since'] != since) or item['name'] in existing \
                    or not _available(env, item):
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
        'cumulative': ms.get('cumulative', False), 'ignore_period': ms.get('ignore_period', False),
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


def _upgrade_commercial_v10(env):
    """19.0.10.0.0: "Seguimiento comercial" como las láminas 0 a 4 y 10 del Reporte Comercial.

    * Acomoda los elementos de fábrica que ya existen (secuencia, ancho y
      números sobre las barras) y les pone las notas con valores, solo si
      todavía tienen la nota de fábrica anterior.
    * Quita el "Embudo por segmento" (lo reemplaza la tabla Totales / SR / R).
    * Agrega los elementos nuevos.
    """
    dashboard = env.ref('%s.%s' % (MODULE, COMMERCIAL['xmlid']), raise_if_not_found=False)
    if not dashboard:
        return []
    dashboard.widget_ids.filtered(lambda w: w.name in OLD_COMMERCIAL_NAMES).unlink()
    dashboard.description = COMMERCIAL['description']
    for item in COMMERCIAL['widgets']:
        if item.get('since') == V10:
            continue
        widget = dashboard.widget_ids.filtered(lambda w, item=item: w.name == item['name']
                                               and w.widget_type == item['type'])[:1]
        if not widget:
            continue
        vals = {'sequence': item['sequence']}
        if item['type'] != 'section':
            vals['width'] = item.get('width', '12')
        if item.get('show_values'):
            vals['show_values'] = True
        old_subtitle = OLD_COMMERCIAL_SUBTITLES.get(item['name'])
        if old_subtitle and (widget.subtitle or '') == old_subtitle:
            vals['subtitle'] = item.get('subtitle')
        widget.write(vals)
    return _ensure_widgets(env, since=V10, xmlids=[COMMERCIAL['xmlid']])


def _fix_commercial_v10_1(env):
    """19.0.10.0.1: dominio de origen de leads como la lámina 10 y color del acumulado
    visible en modo oscuro. Solo cambia lo que sigue igual a como se creó."""
    dashboard = env.ref('%s.%s' % (MODULE, COMMERCIAL['xmlid']), raise_if_not_found=False)
    if not dashboard:
        return
    origin = dashboard.widget_ids.filtered(lambda w: w.domain == OLD_ORIGIN_DOMAIN and w.name in (
        'Leads Sin Recompra por canal de origen', 'Origen de leads Sin Recompra (tabla)'))
    origin.write({'domain': ORIGIN_DOMAIN})
    dashboard.widget_ids.measure_ids.filtered(
        lambda m: m.code == 'acumulado' and m.color == OLD_CUMULATIVE_COLOR).write({'color': CUMULATIVE_COLOR})


def _upgrade_week_report_v12(env):
    """19.0.12.0.0: gráficas del Reporte semanal Dirección que faltaban según las
    sesiones del 28/10 y 13/11 y el documento base (desviación por cuenta
    analítica, costos y margen NeoData por proyecto, balance financiero,
    histórico semanal, margen semanal y diferencia de costos por partida).

    * Quita el combinado "Indicadores de costos y venta por semana" (se separa
      en indicador de costos e indicador de venta, como la lámina).
    * Acomoda secuencia y ancho de los elementos de fábrica que ya existen.
    * Agrega los elementos nuevos (since=V12). Lo que el usuario agregó se queda.
    """
    dashboard = env.ref('%s.%s' % (MODULE, WEEK_REPORT['xmlid']), raise_if_not_found=False)
    if not dashboard:
        return []
    dashboard.widget_ids.filtered(lambda w: w.name in OLD_WEEK_NAMES).unlink()
    dashboard.description = WEEK_REPORT['description']
    for item in WEEK_REPORT['widgets']:
        if item.get('since') == V12:
            continue
        widget = dashboard.widget_ids.filtered(lambda w, item=item: w.name == item['name']
                                               and w.widget_type == item['type'])[:1]
        if widget:
            vals = {'sequence': item['sequence']}
            if not item.get('hidden'):
                vals['width'] = item.get('width', '12')
            widget.write(vals)
    return _ensure_widgets(env, since=V12, xmlids=[WEEK_REPORT['xmlid']])
