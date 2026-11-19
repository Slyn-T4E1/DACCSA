# -*- coding: utf-8 -*-
"""Genera el tablero "Reporte semanal Dirección" (Tableros de Odoo) en JSON.

Etapa 5. No forma parte del módulo en ejecución: es una herramienta de
desarrollo. Para cambiar el tablero se edita este archivo y se vuelve a
generar:

    python3 tools/generate_week_report_dashboard.py

Escribe data/files/week_report_dashboard.json, que el módulo carga en
data/spreadsheet_dashboard.xml.

El tablero muestra la SEMANA VIGENTE (la última semana cerrada; si no hay
cerradas, la última). Para ver otra semana se usa la pestaña "Resumen" de
la semana de reporte. La tendencia muestra todas las semanas.

Contenido (una sola hoja, Tableros solo muestra la primera):
  * Indicadores: costo planeado, costo real, desviación acumulada (% de
    optimización), cambio vs semana anterior, venta semanal NeoData y margen
    operativo global.
  * Gráfica "Balance de costos por partida" (planeado vs real).
  * Gráfica "Indicadores de costos y venta" (balance y venta semanal por semana).
  * Tabla "Balance de costos por partida" con diferencias vs semana anterior.
  * Tabla "Margen operativo al momento – proyectos" con alerta de margen bajo.
Filtro global: Proyecto (para quitar o dejar solo algunos proyectos).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'data', 'files', 'week_report_dashboard.json')
MODULE = 'custom_business_reports'

M_WEEK = 'business.report.week'
M_PROJECT = 'business.report.week.project'
M_PARTIDA = 'business.report.week.partida'
M_COST = 'business.report.dashboard.cost'
M_TREND = 'business.report.dashboard.trend'

PARTIDAS = [('materiales', 'Materiales'), ('mano_obra', 'Mano de obra'),
            ('subcontratistas', 'Subcontratistas'), ('equipo_herramienta', 'Equipo y herramienta'),
            ('indirectos', 'Indirectos')]
MAX_PROJECTS = 15     # renglones de la tabla de márgenes

# ---------------------------------------------------------------------------
# Filtro global
# ---------------------------------------------------------------------------
F_PROJECT = 'ccr-week-flt-proyecto'
GLOBAL_FILTERS = [
    {'id': F_PROJECT, 'type': 'relation', 'label': 'Proyecto',
     'modelName': 'account.analytic.account', 'defaultValueDisplayNames': []},
]


def matching(field='analytic_account_id'):
    return {F_PROJECT: {'chain': field, 'type': 'many2one'}} if field else {}


CURRENT = ['week_is_current', '=', True]

# ---------------------------------------------------------------------------
# Fuentes de datos
# ---------------------------------------------------------------------------
PIVOTS = {
    # 1. Partidas de la semana vigente (todos los proyectos)
    '1': {'name': 'Partidas semana vigente', 'model': M_PARTIDA, 'rows': ['partida'],
          'domain': [CURRENT],
          'measures': ['planned_amount', 'real_amount', 'deviation', 'planned_delta', 'real_delta']},
    # 2. Proyectos de la semana vigente
    '2': {'name': 'Proyectos semana vigente', 'model': M_PROJECT, 'rows': ['analytic_account_id'],
          'domain': [CURRENT],
          'measures': ['estimate_amount', 'real_total', 'operating_margin', 'neodata_advance']},
}

LISTS = {
    # Datos de la semana vigente (nombre, fecha, alerta de margen)
    '1': {'id': '1', 'name': 'Semana vigente', 'model': M_WEEK,
          'columns': ['name', 'date', 'state', 'margin_alert_pct'],
          'domain': [['is_current', '=', True]], 'context': {},
          'orderBy': [{'name': 'date', 'asc': False}], 'fieldMatching': {}},
}


def pivot_json(pid, spec):
    return {
        'type': 'ODOO', 'id': pid, 'formulaId': pid, 'name': spec['name'],
        'model': spec['model'], 'domain': spec['domain'], 'context': {},
        'columns': [], 'rows': [{'fieldName': f} for f in spec['rows']],
        'measures': [{'id': m, 'fieldName': m} for m in spec['measures']],
        'sortedColumn': None, 'fieldMatching': matching(),
    }


def pv(pid, measure, *groups):
    args = ','.join(['%s' % pid, '"%s"' % measure] + ['"%s"' % g if not isinstance(g, int) else str(g)
                                                      for g in groups])
    return 'IFERROR(PIVOT.VALUE(%s),0)' % args


def short(cell):
    """Número abreviado: millones ("m") o miles ("k") según el tamaño."""
    return 'IF(ABS({0})>=1000000,FORMAT.LARGE.NUMBER({0},"m"),FORMAT.LARGE.NUMBER({0},"k"))'.format(cell)


# ---------------------------------------------------------------------------
# Hoja "Datos" (oculta): indicadores
# ---------------------------------------------------------------------------
data_cells = {
    'A1': 'Indicador', 'B1': 'Valor', 'C1': 'Texto',
    'A2': 'Costo planeado', 'B2': '=' + pv(1, 'planned_amount'),
    'A3': 'Costo real', 'B3': '=' + pv(1, 'real_amount'),
    'A4': 'Desviación acumulada', 'B4': '=B2-B3',
    'A5': '% optimización', 'B5': '=IFERROR(B4/B2,0)',
    'A6': 'Cambio de la desviación vs semana anterior', 'B6': '=%s-%s' % (pv(1, 'planned_delta'), pv(1, 'real_delta')),
    'A7': 'Venta semanal (avance NeoData)', 'B7': '=' + pv(2, 'neodata_advance'),
    'A8': 'Venta real (estimado autorizado)', 'B8': '=' + pv(2, 'estimate_amount'),
    'A9': 'Costo real de los proyectos', 'B9': '=' + pv(2, 'real_total'),
    'A10': 'Margen operativo global', 'B10': '=B8-B9',
    'A11': '% margen operativo global', 'B11': '=IFERROR(B10/B8,0)',
    'A12': 'Alerta de margen bajo', 'B12': '=IFERROR(ODOO.LIST(1,1,"margin_alert_pct"),0.15)',
    'A13': 'Semana vigente', 'B13': '=IFERROR(ODOO.LIST(1,1,"name"),"Sin semanas de reporte")',
    'C2': '=' + short('B2'), 'C3': '=' + short('B3'),
    'C4': '=' + short('B4'), 'C5': '=TEXT(B5,"0.00%")&" de optimización"',
    # Texto con flecha (al concatenar se pierde el formato, por eso TEXT)
    'C6': '=IF(B6>=0,"▲ $","▼ $")&IF(ABS(B6)>=1000000,TEXT(ABS(B6)/1000000,"#,##0.0")&"m",'
          'TEXT(ABS(B6)/1000,"#,##0")&"k")',
    'C7': '=' + short('B7'),
    'C10': '="$"&TEXT(B10/1000000,"#,##0.0")&" M sobre venta real"',
    'C11': '=B11',
}

# ---------------------------------------------------------------------------
# Hoja principal
# ---------------------------------------------------------------------------
ROW_CHARTS = 8           # renglón (base 1) del título de las gráficas
ROW_COST = 28            # título de la tabla de partidas
ROW_MARGIN = ROW_COST + 10
main_cells = {
    'A1': 'Reporte Semanal de Dirección · Proyectos en curso',
    'A2': '="Semana vigente: "&Datos!B13&"   ·   Para otra semana: Proyecto › Reportes › Semanas de reporte › Resumen"',
    'A%d' % ROW_CHARTS: 'Balance de costos por partida y tendencia semanal',
}
main_styles = {'A1': 1, 'A2': 5, 'A%d' % ROW_CHARTS: 2}
main_formats = {}
cfs = []

# Tabla de partidas
r = ROW_COST
main_cells['A%d' % r] = 'Balance de costos por partida (Σ proyectos en análisis)'
main_styles['A%d' % r] = 2
r += 1
headers = ['Posición', 'Planeado', 'Real', 'Diferencia', '%', 'Δ planeado vs sem. ant.', 'Δ real vs sem. ant.']
for i, h in enumerate(headers):
    main_cells['%s%d' % ('ABCDEFG'[i], r)] = h
main_styles['A%d:G%d' % (r, r)] = 3
first = r + 1
for key, label in PARTIDAS:
    r += 1
    main_cells['A%d' % r] = label
    main_cells['B%d' % r] = '=' + pv(1, 'planned_amount', 'partida', key)
    main_cells['C%d' % r] = '=' + pv(1, 'real_amount', 'partida', key)
    main_cells['D%d' % r] = '=B%d-C%d' % (r, r)
    main_cells['E%d' % r] = '=IFERROR(D%d/B%d,0)' % (r, r)
    main_cells['F%d' % r] = '=' + pv(1, 'planned_delta', 'partida', key)
    main_cells['G%d' % r] = '=' + pv(1, 'real_delta', 'partida', key)
r += 1
main_cells['A%d' % r] = 'Sumatoria'
for col in 'BCDFG':
    main_cells['%s%d' % (col, r)] = '=SUM(%s%d:%s%d)' % (col, first, col, r - 1)
main_cells['E%d' % r] = '=IFERROR(D%d/B%d,0)' % (r, r)
main_styles['A%d:G%d' % (r, r)] = 4
main_formats['B%d:D%d' % (first, r)] = 3
main_formats['F%d:G%d' % (first, r)] = 3
main_formats['E%d:E%d' % (first, r)] = 1
cfs.append({'id': 'ccr-cf-dev-pos', 'ranges': ['D%d:E%d' % (first, r)],
            'rule': {'type': 'CellIsRule', 'operator': 'isGreaterOrEqualTo', 'values': ['0'],
                     'style': {'fillColor': '#DCFCE7', 'textColor': '#15803D', 'bold': True}}})
cfs.append({'id': 'ccr-cf-dev-neg', 'ranges': ['D%d:E%d' % (first, r)],
            'rule': {'type': 'CellIsRule', 'operator': 'isLessThan', 'values': ['0'],
                     'style': {'fillColor': '#FEE2E2', 'textColor': '#B91C1C', 'bold': True}}})

# Tabla de márgenes por proyecto (renglones por posición en la tabla dinámica)
r = ROW_MARGIN
main_cells['A%d' % r] = 'Margen operativo al momento – proyectos'
main_styles['A%d' % r] = 2
main_cells['E%d' % r] = '="Rojo: margen menor a "&TEXT(Datos!B12,"0%")&" (se cambia en la semana)"'
main_styles['E%d' % r] = 5
r += 1
for i, h in enumerate(['Proyecto', 'Venta real', 'Costo real', 'Margen operativo', '% Margen']):
    main_cells['%s%d' % ('ABCDE'[i], r)] = h
main_styles['A%d:E%d' % (r, r)] = 3
# Resultado global arriba (el número de proyectos cambia cada semana)
r += 1
first = r
main_cells['A%d' % r] = 'Resultado global'
main_cells['B%d' % r] = '=Datos!B8'
main_cells['C%d' % r] = '=Datos!B9'
main_cells['D%d' % r] = '=Datos!B10'
main_cells['E%d' % r] = '=Datos!B11'
main_styles['A%d:E%d' % (r, r)] = 4
for i in range(1, MAX_PROJECTS + 1):
    r += 1
    main_cells['A%d' % r] = '=IFERROR(PIVOT.HEADER(2,"#analytic_account_id",%d),"")' % i
    main_cells['B%d' % r] = '=IF(A{0}="","",{1})'.format(r, pv(2, 'estimate_amount', '#analytic_account_id', i))
    main_cells['C%d' % r] = '=IF(A{0}="","",{1})'.format(r, pv(2, 'real_total', '#analytic_account_id', i))
    main_cells['D%d' % r] = '=IF(A{0}="","",B{0}-C{0})'.format(r)
    main_cells['E%d' % r] = '=IF(A{0}="","",IFERROR(D{0}/B{0},0))'.format(r)
main_formats['B%d:D%d' % (first, r)] = 3
main_formats['E%d:E%d' % (first, r)] = 1
cfs.append({'id': 'ccr-cf-margin-low', 'ranges': ['E%d:E%d' % (first, r)],
            'rule': {'type': 'CellIsRule', 'operator': 'isLessThan', 'values': ['=Datos!$B$12'],
                     'style': {'fillColor': '#FEE2E2', 'textColor': '#B91C1C', 'bold': True}}})
cfs.append({'id': 'ccr-cf-margin-ok', 'ranges': ['E%d:E%d' % (first, r)],
            'rule': {'type': 'CellIsRule', 'operator': 'isGreaterOrEqualTo', 'values': ['=Datos!$B$12'],
                     'style': {'fillColor': '#DCFCE7', 'textColor': '#15803D', 'bold': True}}})
MAIN_ROWS = r + 3

# ---------------------------------------------------------------------------
# Indicadores (scorecards) y gráficas
# ---------------------------------------------------------------------------
SCORECARDS = [
    # id, título, valor, línea base (texto), color
    ('ccr-wk-planned', 'Costo planeado', 'Datos!C2', '', 'NeoData, Σ partidas', '#EFF6FF'),
    ('ccr-wk-real', 'Costo real', 'Datos!C3', '', 'Odoo, al corte', '#F9FAFB'),
    ('ccr-wk-dev', 'Desviación', 'Datos!C4', 'Datos!C5', '', '#F0FDF4'),
    ('ccr-wk-dev-delta', 'Vs sem. anterior', 'Datos!C6', '', 'cambio de la desviación', '#F0FDF4'),
    ('ccr-wk-sale', 'Venta semanal', 'Datos!C7', '', 'Σ avance NeoData', '#FFF7ED'),
    ('ccr-wk-margin', 'Margen operativo', 'Datos!C11', 'Datos!C10', '', '#F0FDF4'),
]


def scorecard_figure(i, cid, title, cell, baseline, note, bg):
    return {
        'id': cid, 'col': 0, 'row': 2, 'offset': {'x': i * 205, 'y': 6},
        'width': 195, 'height': 105, 'tag': 'chart',
        'data': {'type': 'scorecard', 'chartId': cid, 'keyValue': cell, 'baseline': baseline,
                 'baselineMode': 'text', 'baselineColorUp': '#00A04A', 'baselineColorDown': '#DC6965',
                 'baselineDescr': {'text': note},
                 'title': {'text': title, 'bold': True, 'color': '#434343'},
                 'background': bg, 'humanize': False},
    }


def chart_figure(cid, title, chart_type, model, group_by, measure, domain, x, stacked=False, context=None):
    return {
        'id': cid, 'col': 0, 'row': ROW_CHARTS, 'offset': {'x': x, 'y': 0},
        'width': 600, 'height': 360, 'tag': 'chart',
        'data': {
            'type': chart_type, 'chartId': cid,
            'title': {'text': title, 'bold': True, 'fontSize': 16, 'color': '#1F2937'},
            'background': '#FFFFFF', 'legendPosition': 'top', 'stacked': stacked,
            'verticalAxisPosition': 'left', 'dataSets': [],
            'metaData': {'groupBy': group_by, 'measure': measure, 'order': None,
                         'resModel': model, 'mode': chart_type.replace('odoo_', '')},
            'searchParams': {'comparison': None, 'context': context or {}, 'domain': domain,
                             'groupBy': group_by, 'orderBy': []},
            'axesDesign': {'x': {'title': {'text': ''}}, 'y': {'title': {'text': ''}}},
            'fieldMatching': matching(),
        },
    }


CHARTS = [
    chart_figure('ccr-wk-chart-cost', 'Balance de costos por partida (semana vigente)', 'odoo_bar', M_COST,
                 ['partida', 'kind'], 'amount', [['is_current', '=', True]], 0),
    chart_figure('ccr-wk-chart-trend', 'Indicadores de costos y venta por semana', 'odoo_line', M_TREND,
                 ['week_date:day', 'serie'], 'amount', [], 625, context={'fill_temporal': False}),
]
CHART_MENUS = {
    'ccr-wk-chart-cost': '%s.menu_week_report_weeks' % MODULE,
    'ccr-wk-chart-trend': '%s.menu_week_report_projects' % MODULE,
}


def build():
    styles = {
        '1': {'bold': True, 'fontSize': 18, 'textColor': '#1F2937'},
        '2': {'bold': True, 'fontSize': 13, 'textColor': '#714B67'},
        '3': {'bold': True, 'fillColor': '#2F5BEA', 'textColor': '#FFFFFF'},
        '4': {'bold': True, 'fillColor': '#F3F4F6'},
        '5': {'italic': True, 'textColor': '#6B7280'},
    }
    formats = {'1': '0.00%', '2': '#,##0', '3': '[$$]#,##0.00'}
    figures = [scorecard_figure(i, *sc) for i, sc in enumerate(SCORECARDS)] + CHARTS
    main_sheet = {
        'id': 'ccr-wk-sheet-main', 'name': 'Reporte semanal Dirección',
        'colNumber': 10, 'rowNumber': MAIN_ROWS,
        'rows': {'0': {'size': 40}}, 'cols': {'0': {'size': 300}, '1': {'size': 150}, '2': {'size': 150},
                                              '3': {'size': 150}, '4': {'size': 110}, '5': {'size': 170},
                                              '6': {'size': 170}},
        'merges': [], 'cells': main_cells, 'styles': main_styles, 'formats': main_formats,
        'borders': {}, 'conditionalFormats': cfs, 'dataValidationRules': [],
        'figures': figures, 'tables': [], 'areGridLinesVisible': False, 'isVisible': True,
        'headerGroups': {'ROW': [], 'COL': []}, 'comments': {},
    }
    data_sheet = {
        'id': 'ccr-wk-sheet-data', 'name': 'Datos', 'colNumber': 4, 'rowNumber': 20,
        'rows': {}, 'cols': {'0': {'size': 300}}, 'merges': [], 'cells': data_cells,
        'styles': {'A1:C1': 4}, 'formats': {'B5': 1, 'B11:C11': 1, 'B12': 1, 'B2:B4': 3, 'B6:B10': 3},
        'borders': {}, 'conditionalFormats': [], 'dataValidationRules': [], 'figures': [], 'tables': [],
        'areGridLinesVisible': True, 'isVisible': False,
        'headerGroups': {'ROW': [], 'COL': []}, 'comments': {},
    }
    return {
        'version': '18.5.10',
        'sheets': [main_sheet, data_sheet],
        'styles': styles, 'formats': formats, 'borders': {},
        'revisionId': 'START_REVISION', 'uniqueFigureIds': True,
        'settings': {'locale': {'name': 'Spanish (MX)', 'code': 'es_MX', 'thousandsSeparator': ',',
                                'decimalSeparator': '.', 'dateFormat': 'dd/mm/yyyy',
                                'timeFormat': 'hh:mm:ss', 'formulaArgSeparator': ',', 'weekStart': 1}},
        'pivots': {pid: pivot_json(pid, spec) for pid, spec in PIVOTS.items()},
        'pivotNextId': len(PIVOTS) + 1,
        'customTableStyles': {},
        'globalFilters': GLOBAL_FILTERS,
        'lists': LISTS, 'listNextId': len(LISTS) + 1,
        'chartOdooMenusReferences': CHART_MENUS,
    }


if __name__ == '__main__':
    doc = build()
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print('Tablero generado en', os.path.normpath(OUT))
