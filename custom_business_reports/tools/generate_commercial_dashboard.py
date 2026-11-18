# -*- coding: utf-8 -*-
"""Genera el tablero "Seguimiento comercial" (Tableros de Odoo) en JSON.

No forma parte del módulo en ejecución: es una herramienta de desarrollo.
Para cambiar el tablero se edita este archivo y se vuelve a generar:

    python3 tools/generate_commercial_dashboard.py

Escribe dos tableros que el módulo carga en data/spreadsheet_dashboard.xml:
  data/files/commercial_dashboard.json        (indicadores, gráficas, embudo)
  data/files/commercial_lists_dashboard.json  (listados por estatus) Todas las gráficas leen datos vivos de
crm.lead con los campos de la Etapa 1 y 2 y excluyen "Ganados en 0's".

Estructura:
  Tablero "Seguimiento comercial":
    Hoja "Seguimiento comercial": indicadores, gráficas y embudo por segmento.
    Hoja "Datos" (oculta): cálculos de los indicadores.
  Tablero "Seguimiento comercial · Listados" (Tableros muestra solo la
  primera hoja, por eso los listados van en un tablero aparte):
    ganados, perdidos, pipeline enviado, en pausa, cancelados y
    oportunidades lentas (15 renglones cada uno).
"""
import json
import os

MODEL = 'crm.lead'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'data', 'files', 'commercial_dashboard.json')
OUT_LISTS = os.path.join(HERE, '..', 'data', 'files', 'commercial_lists_dashboard.json')
MODULE = 'custom_business_reports'

# ---------------------------------------------------------------------------
# Filtros globales del tablero
# ---------------------------------------------------------------------------
F_PERIOD = 'ccr-flt-periodo'    # Periodo (fecha de creación o de cierre según la gráfica)
F_USER = 'ccr-flt-vendedor'     # Vendedor
GLOBAL_FILTERS = [
    {'id': F_PERIOD, 'type': 'date', 'label': 'Periodo', 'defaultValue': 'this_year'},
    {'id': F_USER, 'type': 'relation', 'label': 'Vendedor', 'modelName': 'res.users',
     'defaultValueDisplayNames': []},
]


def matching(date_field=None):
    """Relación de cada filtro global con los campos de la fuente de datos.

    date_field=None: la fuente no se filtra por periodo (p. ej. histórico o
    pipeline vigente).
    """
    res = {F_USER: {'chain': 'user_id', 'type': 'many2one'}}
    if date_field:
        res[F_PERIOD] = {'chain': date_field, 'type': 'datetime', 'offset': 0}
    return res


# Incluye oportunidades archivadas (Odoo archiva las perdidas)
WITH_ARCHIVED = ['active', 'in', [True, False]]
OPP = ['type', '=', 'opportunity']
NOT_EXCLUDED = ['report_stage_group', '!=', 'excluido']

# ---------------------------------------------------------------------------
# Tablas dinámicas (alimentan indicadores y embudo)
# ---------------------------------------------------------------------------
PIVOTS = {
    # 1. Cotizaciones cerradas (ganadas / perdidas por segmento), por fecha de cierre
    '1': {'name': 'Cerradas', 'rows': ['report_close_status'],
          'domain': [OPP, WITH_ARCHIVED, ['report_close_status', '!=', False]],
          'measures': ['__count', 'expected_revenue'], 'match': 'date_closed'},
    # 2. Invitaciones a cotizar (atendidas / no atendidas) por segmento, por fecha de creación
    '2': {'name': 'Invitaciones', 'rows': ['report_invitation_status', 'report_segment'],
          'domain': [OPP, WITH_ARCHIVED, ['report_invitation_status', '!=', False]],
          'measures': ['__count'], 'match': 'create_date'},
    # 3. Pipeline enviado vigente (pendiente de respuesta), sin filtro de periodo
    '3': {'name': 'Pipeline enviado', 'rows': ['report_segment'],
          'domain': [OPP, ['report_open_status', '=', 'enviada'], ['won_status', '=', 'pending']],
          'measures': ['__count', 'expected_revenue'], 'match': None},
}


def pivot_json(pid, spec):
    return {
        'type': 'ODOO',
        'id': pid,
        'formulaId': pid,
        'name': spec['name'],
        'model': MODEL,
        'domain': spec['domain'],
        'context': {},
        'columns': [],
        'rows': [{'fieldName': f} for f in spec['rows']],
        'measures': [{'id': m, 'fieldName': m} for m in spec['measures']],
        'sortedColumn': None,
        'fieldMatching': matching(spec['match']),
    }


# ---------------------------------------------------------------------------
# Celdas de la hoja "Datos" (oculta)
# ---------------------------------------------------------------------------
def pv(pid, measure, *groups):
    """Fórmula PIVOT.VALUE protegida: devuelve 0 si el grupo no existe."""
    args = ','.join(['%s' % pid, '"%s"' % measure] + ['"%s"' % g for g in groups])
    return 'IFERROR(PIVOT.VALUE(%s),0)' % args


SEGMENTS = [('sin_recompra', 'Sin recompra'), ('recompra', 'Recompra'), ('inadecuado', 'Inadecuado')]

data_cells = {
    'A1': 'Indicador', 'B1': 'Valor', 'C1': 'Texto',
    # Ganados / perdidos
    'A2': 'Ganados', 'B2': '=' + '+'.join(pv(1, '__count', 'report_close_status', s) for s in
                                           ('ganado_sin_recompra', 'ganado_recompra', 'ganado_otro')),
    'A3': 'Perdidos', 'B3': '=' + '+'.join(pv(1, '__count', 'report_close_status', s) for s in
                                            ('perdido_sin_recompra', 'perdido_recompra', 'perdido_otro')),
    'A4': 'Venta ganada', 'B4': '=' + '+'.join(pv(1, 'expected_revenue', 'report_close_status', s) for s in
                                               ('ganado_sin_recompra', 'ganado_recompra', 'ganado_otro')),
    # Invitaciones
    'A5': 'Invitaciones', 'B5': '=' + pv(2, '__count'),
    'A6': 'Atendidas', 'B6': '=B5-' + pv(2, '__count', 'report_invitation_status', 'no_atendido'),
    # Razones
    'A7': '% de bateo (ganados / atendidos)', 'B7': '=IFERROR(B2/B6,0)',
    'A8': 'Efectividad de cierre (G / G+P)', 'B8': '=IFERROR(B2/(B2+B3),0)',
    'A9': 'Pipeline enviado (monto)', 'B9': '=' + pv(3, 'expected_revenue'),
    'A10': 'Pipeline enviado (cotizaciones)', 'B10': '=' + pv(3, '__count'),
    # Textos para los indicadores (números grandes abreviados)
    'C2': '=FORMAT.LARGE.NUMBER(B2)', 'C3': '=FORMAT.LARGE.NUMBER(B3)', 'C4': '=FORMAT.LARGE.NUMBER(B4,"m")',
    'C5': '=FORMAT.LARGE.NUMBER(B5)', 'C6': '=FORMAT.LARGE.NUMBER(B6)', 'C7': '=B7', 'C8': '=B8',
    'C9': '=FORMAT.LARGE.NUMBER(B9,"m")', 'C10': '=B10',
}

# ---------------------------------------------------------------------------
# Hoja principal: embudo por segmento (tabla con fórmulas)
# ---------------------------------------------------------------------------
FUNNEL_ROW = 40       # renglón (base 1) del encabezado del embudo
funnel_cells = {}
funnel_cells['A%d' % FUNNEL_ROW] = 'Concepto'
funnel_cols = [('B', None, 'Total')] + [(c, seg, label) for c, (seg, label) in zip('CDE', SEGMENTS)]
for col, _seg, label in funnel_cols:
    funnel_cells['%s%d' % (col, FUNNEL_ROW)] = label


def inv(seg, statuses):
    """Suma de invitaciones de un segmento (None = todos) en ciertos estatus."""
    parts = []
    for st in statuses:
        parts.append(pv(2, '__count', 'report_invitation_status', st, 'report_segment', seg) if seg
                     else pv(2, '__count', 'report_invitation_status', st))
    return '+'.join(parts)


def closed(seg, prefix):
    key = {'sin_recompra': 'sin_recompra', 'recompra': 'recompra', 'inadecuado': 'otro'}
    if seg:
        return pv(1, '__count', 'report_close_status', '%s_%s' % (prefix, key[seg]))
    return '+'.join(pv(1, '__count', 'report_close_status', '%s_%s' % (prefix, k))
                    for k in ('sin_recompra', 'recompra', 'otro'))


ATTENDED = ['atendido_sin_recompra', 'atendido_recompra', 'atendido_inadecuado', 'atendido_sin_segmento']
funnel_rows = [
    ('Invitaciones a cotizar', lambda c, s: '=%s' % inv(s, ATTENDED + ['no_atendido'])),
    ('Atendidos (cotizados)', lambda c, s: '=%s' % inv(s, ATTENDED)),
    ('Declinados (no se participó)', lambda c, s: '=%s' % inv(s, ['no_atendido'])),
    ('Ganados', lambda c, s: '=%s' % closed(s, 'ganado')),
    ('Perdidos', lambda c, s: '=%s' % closed(s, 'perdido')),
    ('Pendientes de respuesta', lambda c, s: '=%s%d-%s%d-%s%d' % (c, FUNNEL_ROW + 2, c, FUNNEL_ROW + 4, c, FUNNEL_ROW + 5)),
    ('% de bateo (G / atendidos)', lambda c, s: '=IFERROR(%s%d/%s%d,0)' % (c, FUNNEL_ROW + 4, c, FUNNEL_ROW + 2)),
    ('Efectividad de cierre (G / G+P)', lambda c, s: '=IFERROR(%s%d/(%s%d+%s%d),0)' % (c, FUNNEL_ROW + 4, c, FUNNEL_ROW + 4, c, FUNNEL_ROW + 5)),
]
for i, (label, fn) in enumerate(funnel_rows, start=1):
    r = FUNNEL_ROW + i
    funnel_cells['A%d' % r] = label
    for col, seg, _label in funnel_cols:
        funnel_cells['%s%d' % (col, r)] = fn(col, seg)
PCT_RANGE = 'B%d:E%d' % (FUNNEL_ROW + 7, FUNNEL_ROW + 8)

# ---------------------------------------------------------------------------
# Gráficas (leen datos vivos con groupBy)
# ---------------------------------------------------------------------------
CHARTS = [
    # id, título, groupBy, medida, dominio, campo de fecha para "Periodo", menú, col, row
    ('ccr-chart-invitations', 'Invitaciones a cotizar por mes',
     ['create_date:month', 'report_invitation_status'], '__count',
     [OPP, WITH_ARCHIVED, ['report_invitation_status', '!=', False]], 'create_date',
     'menu_business_report_invitations', 0, 7),
    ('ccr-chart-invitations-q', 'Histórico de invitaciones por trimestre',
     ['create_date:quarter', 'report_invitation_status'], '__count',
     [OPP, WITH_ARCHIVED, ['report_invitation_status', '!=', False]], None,
     'menu_business_report_invitations', 5, 7),
    ('ccr-chart-close', 'Ganados y perdidos por mes de cierre',
     ['date_closed:month', 'report_close_status'], '__count',
     [OPP, WITH_ARCHIVED, ['report_close_status', '!=', False]], 'date_closed',
     'menu_business_report_close_status', 0, 23),
    ('ccr-chart-sales', 'Venta por mes de cierre',
     ['date_closed:month', 'report_segment'], 'expected_revenue',
     [OPP, ['won_status', '=', 'won'], NOT_EXCLUDED], 'date_closed',
     'menu_business_report_sales', 5, 23),
    ('ccr-chart-lost-reasons', 'Razones de pérdida',
     ['lost_reason_id'], '__count',
     [OPP, ['active', '=', False], ['won_status', '=', 'lost']], 'date_closed',
     'menu_business_list_lost', 5, 39),
    ('ccr-chart-prospecting', 'Prospección Sin recompra por etapa (mes de creación)',
     ['create_date:month', 'stage_id'], '__count',
     [OPP, WITH_ARCHIVED, ['report_segment', '=', 'sin_recompra'],
      ['report_stage_group', 'in', ['prospeccion', 'por_enviar', 'declinado']]], 'create_date',
     'menu_business_list_prospecting', 0, 52),
]


def chart_figure(cid, title, group_by, measure, domain, date_field, col, row):
    # col 0 = columna izquierda; cualquier otro valor = columna derecha.
    # Se posiciona con offset para no depender del ancho de las columnas.
    return {
        'id': cid, 'col': 0, 'row': row, 'offset': {'x': 0 if col == 0 else 620, 'y': 0},
        'width': 590, 'height': 340, 'tag': 'chart',
        'data': {
            'type': 'odoo_bar', 'chartId': cid,
            'title': {'text': title, 'bold': True, 'fontSize': 16, 'color': '#1F2937'},
            'background': '#FFFFFF', 'legendPosition': 'top', 'stacked': True,
            'verticalAxisPosition': 'left', 'dataSets': [],
            'metaData': {'groupBy': group_by, 'measure': measure, 'order': None,
                         'resModel': MODEL, 'mode': 'bar'},
            'searchParams': {'comparison': None, 'context': {}, 'domain': domain,
                             'groupBy': group_by, 'orderBy': []},
            'axesDesign': {'x': {'title': {'text': ''}}, 'y': {'title': {'text': ''}}},
            'fieldMatching': matching(date_field),
        },
    }


SCORECARDS = [
    ('ccr-kpi-sales', 'Venta', 'Datos!C4', '#EFF6FF'),
    ('ccr-kpi-won', 'Ganados', 'Datos!C2', '#EFF6FF'),
    ('ccr-kpi-hit', '% de bateo', 'Datos!C7', '#F0FDF4'),
    ('ccr-kpi-close', 'Efectividad', 'Datos!C8', '#F0FDF4'),
    ('ccr-kpi-pipeline', 'Pipeline enviado', 'Datos!C9', '#FFF7ED'),
    ('ccr-kpi-invitations', 'Invitaciones', 'Datos!C5', '#F9FAFB'),
]


KPI_NOTES = {
    'ccr-kpi-sales': 'ganado por fecha de cierre',
    'ccr-kpi-won': 'cotizaciones ganadas',
    'ccr-kpi-hit': 'ganados / atendidos',
    'ccr-kpi-close': 'ganados / (ganados + perdidos)',
    'ccr-kpi-pipeline': 'pendiente de respuesta, hoy',
    'ccr-kpi-invitations': 'cotizadas + declinadas',
}


def scorecard_figure(i, cid, title, cell, bg):
    return {
        'id': cid, 'col': 0, 'row': 1, 'offset': {'x': i * 200, 'y': 4},
        'width': 190, 'height': 100, 'tag': 'chart',
        'data': {'type': 'scorecard', 'chartId': cid, 'keyValue': cell, 'baseline': '',
                 'baselineMode': 'text', 'baselineColorUp': '#00A04A', 'baselineColorDown': '#DC6965',
                 'baselineDescr': {'text': KPI_NOTES[cid]},
                 'title': {'text': title, 'bold': True, 'color': '#434343'},
                 'background': bg, 'humanize': False},
    }


# ---------------------------------------------------------------------------
# Listados (hoja "Listados")
# ---------------------------------------------------------------------------
LIST_ROWS = 15
LISTS = [
    # id, título, dominio, columnas, orden, campo de fecha para "Periodo"
    ('1', 'Proyectos ganados (más recientes)', [OPP, ['won_status', '=', 'won'], NOT_EXCLUDED],
     ['date_closed', 'partner_id', 'name', 'report_segment', 'expected_revenue'],
     [{'name': 'date_closed', 'asc': False}], 'date_closed'),
    ('2', 'Proyectos perdidos (mayor monto)', [OPP, ['active', '=', False], ['won_status', '=', 'lost']],
     ['date_closed', 'partner_id', 'name', 'report_segment', 'lost_reason_id', 'expected_revenue'],
     [{'name': 'expected_revenue', 'asc': False}], 'date_closed'),
    ('3', 'Pipeline abierto: enviadas pendientes de respuesta',
     [OPP, ['report_open_status', '=', 'enviada'], ['won_status', '=', 'pending']],
     ['create_date', 'partner_id', 'name', 'report_segment', 'report_last_move_date', 'expected_revenue'],
     [{'name': 'expected_revenue', 'asc': False}], None),
    ('4', 'Proyectos en pausa', [OPP, ['report_open_status', '=', 'pausa'], ['won_status', '=', 'pending']],
     ['create_date', 'partner_id', 'name', 'report_segment', 'report_last_move_date', 'expected_revenue'],
     [{'name': 'expected_revenue', 'asc': False}], None),
    ('5', 'Proyectos cancelados', [OPP, ['stage_id.report_close_on_enter', '=', True]],
     ['date_closed', 'partner_id', 'name', 'report_segment', 'expected_revenue'],
     [{'name': 'date_closed', 'asc': False}], 'date_closed'),
    ('6', 'Oportunidades lentas (más tiempo sin movimiento)',
     [OPP, ['won_status', '=', 'pending'], ['report_stage_group', 'in', ['prospeccion', 'por_enviar', 'cotizado']],
      ['stage_id.report_close_on_enter', '=', False]],
     ['report_last_move_date', 'create_date', 'partner_id', 'name', 'stage_id', 'report_segment'],
     [{'name': 'report_last_move_date', 'asc': True}], None),
]


def col_letter(i):
    return 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[i]


def build():
    styles = {
        '1': {'bold': True, 'fontSize': 18, 'textColor': '#1F2937'},           # título
        '2': {'bold': True, 'fontSize': 13, 'textColor': '#714B67'},           # sección
        '3': {'bold': True, 'fillColor': '#1F2A44', 'textColor': '#FFFFFF'},   # encabezado tabla
        '4': {'bold': True},
    }
    formats = {'1': '0.0%', '2': '#,##0', '3': '[$$]#,##0', '4': 'dd/mm/yyyy'}

    # ---------------- Hoja principal ----------------
    main_cells = {
        'A1': 'Seguimiento comercial · Dirección de Nuevos Proyectos',
        'A7': 'Invitaciones a cotizar', 'A23': 'Ganados, perdidos y venta',
        'A%d' % (FUNNEL_ROW - 1): 'Embudo por segmento (periodo seleccionado)',
        'A52': '',
    }
    main_cells.update(funnel_cells)
    main_styles = {'A1': 1, 'A7': 2, 'A23': 2, 'A%d' % (FUNNEL_ROW - 1): 2,
                   'A%d:E%d' % (FUNNEL_ROW, FUNNEL_ROW): 3,
                   'A%d:A%d' % (FUNNEL_ROW + 1, FUNNEL_ROW + 8): 4}
    main_formats = {PCT_RANGE: 1, 'B%d:E%d' % (FUNNEL_ROW + 1, FUNNEL_ROW + 6): 2}
    # Los títulos de sección quedan en el renglón anterior a cada gráfica
    figures = [scorecard_figure(i, *sc) for i, sc in enumerate(SCORECARDS)]
    menus = {}
    for cid, title, gb, measure, domain, date_field, menu, col, row in CHARTS:
        figures.append(chart_figure(cid, title, gb, measure, domain, date_field, col, row))
        menus[cid] = '%s.%s' % (MODULE, menu)
    main_sheet = {
        'id': 'ccr-sheet-main', 'name': 'Seguimiento comercial',
        'colNumber': 12, 'rowNumber': 80,
        'rows': {'0': {'size': 40}}, 'cols': {'0': {'size': 220}},
        'merges': [], 'cells': main_cells, 'styles': main_styles, 'formats': main_formats,
        'borders': {}, 'conditionalFormats': [], 'dataValidationRules': [],
        'figures': figures, 'tables': [], 'areGridLinesVisible': False, 'isVisible': True,
        'headerGroups': {'ROW': [], 'COL': []}, 'comments': {},
    }

    # ---------------- Hoja de listados ----------------
    list_cells, list_styles, lists = {'A1': 'Seguimiento comercial · Listados por estatus'}, {'A1': 1}, {}
    list_formats = {}
    row = 3
    for lid, title, domain, columns, order, date_field in LISTS:
        list_cells['A%d' % row] = title
        list_styles['A%d' % row] = 2
        row += 1
        for c, field in enumerate(columns):
            list_cells['%s%d' % (col_letter(c), row)] = '=ODOO.LIST.HEADER(%s,"%s")' % (lid, field)
        list_styles['A%d:%s%d' % (row, col_letter(len(columns) - 1), row)] = 3
        for r in range(1, LIST_ROWS + 1):
            for c, field in enumerate(columns):
                list_cells['%s%d' % (col_letter(c), row + r)] = '=ODOO.LIST(%s,%d,"%s")' % (lid, r, field)
        # Fechas sin hora
        for c, field in enumerate(columns):
            if field in ('date_closed', 'create_date', 'report_last_move_date'):
                list_formats['%s%d:%s%d' % (col_letter(c), row + 1, col_letter(c), row + LIST_ROWS)] = 4
        lists[lid] = {
            'id': lid, 'name': title, 'model': MODEL, 'columns': columns, 'domain': domain,
            'context': {}, 'orderBy': order, 'fieldMatching': matching(date_field),
        }
        row += LIST_ROWS + 2
    list_sheet = {
        'id': 'ccr-sheet-lists', 'name': 'Listados comerciales', 'colNumber': 8, 'rowNumber': row + 2,
        'rows': {}, 'cols': {'0': {'size': 110}, '1': {'size': 200}, '2': {'size': 320},
                             '3': {'size': 120}, '4': {'size': 150}, '5': {'size': 150}},
        'merges': [], 'cells': list_cells, 'styles': list_styles, 'formats': list_formats,
        'borders': {}, 'conditionalFormats': [], 'dataValidationRules': [], 'figures': [],
        'tables': [], 'areGridLinesVisible': False, 'isVisible': True,
        'headerGroups': {'ROW': [], 'COL': []}, 'comments': {},
    }

    # ---------------- Hoja de datos (oculta) ----------------
    data_sheet = {
        'id': 'ccr-sheet-data', 'name': 'Datos', 'colNumber': 4, 'rowNumber': 20,
        'rows': {}, 'cols': {'0': {'size': 260}}, 'merges': [], 'cells': data_cells,
        'styles': {'A1:C1': 4}, 'formats': {'B7:C8': 1}, 'borders': {},
        'conditionalFormats': [], 'dataValidationRules': [], 'figures': [], 'tables': [],
        'areGridLinesVisible': True, 'isVisible': False,
        'headerGroups': {'ROW': [], 'COL': []}, 'comments': {},
    }

    main = spreadsheet([main_sheet, data_sheet], styles, formats)
    main.update({
        'pivots': {pid: pivot_json(pid, spec) for pid, spec in PIVOTS.items()},
        'pivotNextId': len(PIVOTS) + 1,
        'chartOdooMenusReferences': menus,
    })
    lists_doc = spreadsheet([list_sheet], styles, formats)
    lists_doc.update({'lists': lists, 'listNextId': len(lists) + 1})
    return main, lists_doc


def spreadsheet(sheets, styles, formats):
    """Estructura base de un documento de Tableros (versión 18.5.10)."""
    return {
        'version': '18.5.10',
        'sheets': sheets,
        'styles': styles, 'formats': formats, 'borders': {},
        'revisionId': 'START_REVISION', 'uniqueFigureIds': True,
        'settings': {'locale': {'name': 'Spanish (MX)', 'code': 'es_MX', 'thousandsSeparator': ',',
                                'decimalSeparator': '.', 'dateFormat': 'dd/mm/yyyy',
                                'timeFormat': 'hh:mm:ss', 'formulaArgSeparator': ',', 'weekStart': 1}},
        'pivots': {}, 'pivotNextId': 1,
        'customTableStyles': {},
        'globalFilters': GLOBAL_FILTERS,
        'lists': {}, 'listNextId': 1,
        'chartOdooMenusReferences': {},
    }


if __name__ == '__main__':
    main_doc, lists_doc = build()
    for path, doc in ((OUT, main_doc), (OUT_LISTS, lists_doc)):
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)
        print('Tablero generado en', os.path.normpath(path))
