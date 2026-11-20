# -*- coding: utf-8 -*-
"""Tableros configurables (Etapa 6).

App "Tableros DACSA": cada tablero se arma con registros, sin programar.

* business.dashboard           Tablero (nombre, quién lo ve, filtros y elementos).
* business.dashboard.filter    Filtro del tablero: periodo, relación (p. ej. vendedor,
                               semana, proyecto), selección o texto.
* business.dashboard.widget    Elemento: sección, indicador, gráfica, tabla o listado.
                               Define el modelo, el dominio y la agrupación.
* business.dashboard.measure   Medida de un elemento: suma/promedio/conteo de un campo,
                               con dominio adicional opcional, o una fórmula.
* business.dashboard.widget.filter
                               Cómo se aplica un filtro a un elemento (qué campo usa,
                               o "no aplicar").

Cálculo (get_dashboard_data):
  1. Se arma el dominio de cada elemento = dominio del elemento + filtros.
  2. Indicadores, gráficas y tablas usan _read_group (respeta los permisos del
     usuario); los listados usan search_read.
  3. Las fórmulas se evalúan con safe_eval. En indicadores pueden usar los
     códigos de otros indicadores; en tablas, los códigos de las columnas del
     mismo renglón y de los indicadores. La división entre cero da 0.

19.0.8.0.0:
  * Tablas con los grupos en columnas (table_transpose): p. ej. meses en
    columnas y una medida por renglón ("Invitaciones a cotizar, mes a mes").
  * Rangos de antigüedad (range_field_id + range_bounds): agrupa por días
    transcurridos desde una fecha (0–30, 31–60, ... más de 180 días).
  * Medidas de otro modelo (source_model_id): p. ej. la meta mensual
    (business.sales.goal) en una gráfica de venta por mes. Se alinean por el
    campo de fecha source_groupby_field con el mismo intervalo.
  * Series como línea o barra y eje derecho por medida (gráficas combinadas).

19.0.9.0.0:
  * Notas y títulos con valores: {código} se cambia por el valor de ese
    indicador (p. ej. "SR {env_sr} ({env_sr_monto})"). Indicador con un
    segundo valor (secondary_code): "16 · $362.5 M".
  * Listados con número de renglón, total, cuenta, resaltado en rojo por
    regla (p. ej. report_age_days > 365) y agrupación por un campo.
  * Números sobre las barras (show_values).
  * Dominios con fechas relativas: context_today() y relativedelta, p. ej.
    [('create_date', '>=', (context_today() - relativedelta(months=2)).strftime('%Y-%m-01'))].
"""
import calendar
import logging
import re
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

WIDGET_TYPES = [
    ('section', 'Sección (título)'),
    ('kpi', 'Indicador'),
    ('chart', 'Gráfica'),
    ('table', 'Tabla'),
    ('list', 'Listado de registros'),
]
CHART_TYPES = [
    ('bar', 'Barras'),
    ('bar_stacked', 'Barras apiladas'),
    ('hbar', 'Barras horizontales'),
    ('line', 'Línea'),
    ('pie', 'Pastel'),
    ('doughnut', 'Dona'),
]
FILTER_TYPES = [
    ('date', 'Periodo (fecha)'),
    ('many2one', 'Relación (registros)'),
    ('selection', 'Selección'),
    ('text', 'Texto'),
]
DATE_PRESETS = [
    ('all', 'Todo'),
    ('this_year', 'Este año'),
    ('last_year', 'Año anterior'),
    ('this_quarter', 'Este trimestre'),
    ('this_month', 'Este mes'),
    ('last_month', 'Mes anterior'),
    ('last_30', 'Últimos 30 días'),
    ('last_12_months', 'Últimos 12 meses'),
    ('custom', 'Personalizado'),
]
INTERVALS = [('day', 'Día'), ('week', 'Semana'), ('month', 'Mes'), ('quarter', 'Trimestre'), ('year', 'Año')]
AGGREGATES = [('sum', 'Suma'), ('avg', 'Promedio'), ('min', 'Mínimo'), ('max', 'Máximo'), ('count', 'Conteo')]
VALUE_FORMATS = [('number', 'Número'), ('number1', 'Número (1 decimal)'), ('integer', 'Entero'),
                 ('monetary', 'Moneda'), ('percent', 'Porcentaje')]
COLOR_MODES = [('none', 'Sin color'), ('sign', 'Verde si ≥ 0, rojo si < 0'),
               ('threshold', 'Rojo si es menor al umbral')]
SERIES_TYPES = [('bar', 'Barras'), ('line', 'Línea')]
SORT_MODES = [('group', 'Por agrupación'), ('value_desc', 'Mayor a menor (1a medida)'),
              ('value_asc', 'Menor a mayor (1a medida)')]
WIDTHS = [('3', '1/4'), ('4', '1/3'), ('6', '1/2'), ('8', '2/3'), ('9', '3/4'), ('12', 'Completo')]
NUMERIC_TYPES = ('integer', 'float', 'monetary')
GROUPABLE_TYPES = ('many2one', 'selection', 'date', 'datetime', 'char', 'boolean', 'integer')

HIGHLIGHT_RULE = re.compile(r'^\s*([\w.]+)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$')
PLACEHOLDER = re.compile(r'\{(\w+)\}')


def _short_number(value, value_format, abbreviate=True, symbol='$'):
    """Número corto para notas (igual que la interfaz): 362.5 M, 45 k, 35.6 %."""
    value = value or 0.0
    if value_format == 'percent':
        return ('%.1f %%' % (value * 100)).replace('.0 %', ' %')
    amount, sign = abs(value), '-' if value < 0 else ''
    if abbreviate and amount >= 1e6:
        text = ('{:,.0f}' if amount >= 1e8 else '{:,.1f}').format(amount / 1e6).removesuffix('.0') + ' M'
    elif abbreviate and amount >= 1e4:
        text = '{:,.0f} k'.format(amount / 1e3)
    elif value_format == 'number1':
        text = '{:,.1f}'.format(amount)
    elif value_format == 'integer' or float(amount).is_integer():
        text = '{:,.0f}'.format(amount)
    else:
        text = '{:,.2f}'.format(amount)
    return sign + (symbol if value_format == 'monetary' else '') + text


# Funciones disponibles en las fórmulas
FORMULA_FUNCTIONS = {
    'abs': abs, 'min': min, 'max': max, 'round': round,
    'div': lambda a, b: (a or 0.0) / b if b else 0.0,
}


def _formula_names(expression):
    """Nombres (códigos) que usa una fórmula, sin las funciones."""
    try:
        names = compile(expression, '<fórmula>', 'eval').co_names
    except SyntaxError as error:
        raise UserError(_('La fórmula "%(formula)s" está mal escrita: %(error)s',
                          formula=expression, error=error)) from error
    return {name for name in names if name not in FORMULA_FUNCTIONS}


def _safe_formula(expression, values):
    """Evalúa una fórmula. Los valores vacíos cuentan como 0 y dividir entre 0 da 0."""
    missing = _formula_names(expression) - set(values)
    if missing:
        raise UserError(_('La fórmula "%(formula)s" usa códigos que no existen: %(codes)s',
                          formula=expression, codes=', '.join(sorted(missing))))
    namespace = dict(FORMULA_FUNCTIONS)
    namespace.update({key: (value or 0.0) for key, value in values.items()})
    try:
        result = safe_eval(expression, namespace)
    except ValueError as error:
        if 'ZeroDivisionError' in str(error):
            return 0.0
        raise UserError(_('Error en la fórmula "%(formula)s": %(error)s', formula=expression, error=error)) from error
    return result if isinstance(result, (int, float)) else 0.0


# ======================================================================
# Tablero
# ======================================================================
class BusinessDashboard(models.Model):
    _name = 'business.dashboard'
    _description = 'Tablero configurable'
    _order = 'sequence, id'

    name = fields.Char(string='Tablero', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category = fields.Char(string='Categoría', help='Agrupa los tableros en el menú lateral (p. ej. "Comercial").')
    description = fields.Text(string='Descripción')
    group_ids = fields.Many2many(
        'res.groups', string='Lo pueden ver',
        help='Grupos que ven el tablero. Vacío = todos los usuarios internos.')
    filter_ids = fields.One2many('business.dashboard.filter', 'dashboard_id', string='Filtros', copy=True)
    widget_ids = fields.One2many('business.dashboard.widget', 'dashboard_id', string='Elementos', copy=True)
    widget_count = fields.Integer(compute='_compute_widget_count', string='Número de elementos')

    @api.depends('widget_ids')
    def _compute_widget_count(self):
        for dashboard in self:
            dashboard.widget_count = len(dashboard.widget_ids)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [dict(vals, name=_('%s (copia)', dashboard.name)) for dashboard, vals in zip(self, vals_list)]

    # ------------------------------------------------------------------
    # API para la interfaz (JS)
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_list(self):
        """Tableros que el usuario puede ver, para el menú lateral."""
        xmlids = self.search([]).get_external_id()
        return [{'id': d.id, 'name': d.name, 'category': d.category or '', 'xmlid': xmlids.get(d.id) or ''}
                for d in self.search([])]

    def get_dashboard_data(self, filter_values=None):
        """Todo lo que la interfaz necesita para pintar el tablero.

        filter_values: {id del filtro (texto): valor}. Si un filtro no viene,
        se usa su valor por omisión.
        """
        self.ensure_one()
        # El usuario debe poder ver el tablero (reglas por grupo). La
        # configuración (campos, modelos) se lee como superusuario porque los
        # usuarios no leen ir.model.fields; los DATOS se consultan con los
        # permisos del usuario (sudo(False) en cada consulta).
        self.check_access('read')
        can_edit = self.env.user.has_group('custom_business_reports.group_dashboard_manager')
        self = self.sudo()  # noqa: PLW0642
        values = self._resolve_filter_values(filter_values or {})
        kpi_values = {}
        widgets = []
        # 1) Indicadores: primero los de datos, luego las fórmulas en el orden
        #    en que sus códigos ya estén calculados.
        kpis = self.widget_ids.filtered(lambda w: w.widget_type == 'kpi')
        kpi_errors = {}
        for widget in kpis.filtered(lambda w: not w.formula):
            try:
                kpi_values[widget.code] = widget._compute_kpi_value(values, kpi_values)
            except Exception as error:  # noqa: BLE001
                kpi_errors[widget.code] = str(error)
                kpi_values[widget.code] = 0.0
        pending = kpis.filtered(lambda w: w.formula)
        while pending:
            ready = pending.filtered(lambda w: _formula_names(w.formula) <= set(kpi_values))
            if not ready:          # códigos inexistentes o referencias circulares
                for widget in pending:
                    kpi_errors[widget.code] = _('La fórmula usa códigos que no existen o se refieren entre sí: %s',
                                                ', '.join(sorted(_formula_names(widget.formula) - set(kpi_values))))
                    kpi_values[widget.code] = 0.0
                break
            for widget in ready:
                try:
                    kpi_values[widget.code] = widget._compute_kpi_value(values, kpi_values)
                except Exception as error:  # noqa: BLE001
                    kpi_errors[widget.code] = str(error)
                    kpi_values[widget.code] = 0.0
            pending -= ready
        kpi_widgets = {w.code: w for w in kpis}
        # 2) Datos de cada elemento visible
        for widget in self.widget_ids.filtered(lambda w: not w.hidden).sorted(lambda w: (w.sequence, w.id)):
            # Título y nota pueden llevar valores de indicadores: {código}
            data = {'id': widget.id, 'type': widget.widget_type,
                    'title': widget._render_text(widget.name, kpi_values, kpi_widgets),
                    'subtitle': widget._render_text(widget.subtitle, kpi_values, kpi_widgets),
                    'width': int(widget.width or 12),
                    'height': widget.height or 320, 'error': False}
            try:
                if widget.widget_type == 'kpi':
                    if widget.code in kpi_errors:
                        raise UserError(kpi_errors[widget.code])
                    data.update(widget._kpi_payload(kpi_values, kpi_widgets))
                elif widget.widget_type == 'chart':
                    data.update(widget._chart_payload(values))
                elif widget.widget_type == 'table':
                    data.update(widget._table_payload(values, kpi_values))
                elif widget.widget_type == 'list':
                    data.update(widget._list_payload(values))
            except Exception as error:  # noqa: BLE001 - se muestra en el elemento, no rompe el tablero
                _logger.warning('Tablero %s, elemento %s: %s', self.name, widget.name, error)
                data['error'] = str(error)
            widgets.append(data)
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'filters': [f._payload(values.get(f.id)) for f in self.filter_ids],
            'widgets': widgets,
            'can_edit': can_edit,
            'currency': {'symbol': self.env.company.currency_id.symbol,
                         'position': self.env.company.currency_id.position},
        }

    def _resolve_filter_values(self, filter_values):
        """Valor efectivo de cada filtro: el que viene de la pantalla o el de omisión."""
        values = {}
        for flt in self.filter_ids:
            key = str(flt.id)
            values[flt.id] = flt._normalize_value(filter_values[key]) if key in filter_values \
                else flt._default_value()
        return values

    def action_open_dashboard(self):
        """Abre el tablero en la app."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'business_dashboard',
            'name': self.name,
            'params': {'dashboard_id': self.id},
        }


# ======================================================================
# Filtro
# ======================================================================
class BusinessDashboardFilter(models.Model):
    _name = 'business.dashboard.filter'
    _description = 'Filtro de tablero'
    _order = 'sequence, id'

    dashboard_id = fields.Many2one('business.dashboard', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Etiqueta', required=True, translate=True)
    filter_type = fields.Selection(FILTER_TYPES, string='Tipo', required=True, default='many2one')
    field_name = fields.Char(
        string='Campo (por omisión)',
        help='Campo al que se aplica en cada elemento cuyo modelo lo tenga (p. ej. user_id, '
             'date_closed, analytic_account_id). Se puede cambiar por elemento en "Filtros aplicados".')
    # Relación
    comodel_id = fields.Many2one('ir.model', string='Modelo de los registros', ondelete='cascade',
                                 help='Para filtros de relación, p. ej. Usuarios o Cuentas analíticas.')
    comodel_name = fields.Char(related='comodel_id.model', string='Modelo (técnico)')
    multiple = fields.Boolean(string='Varios valores', default=True)
    record_domain = fields.Char(string='Registros que se pueden elegir', default='[]',
                                help='Dominio sobre el modelo de los registros.')
    default_domain = fields.Char(
        string='Valor por omisión (dominio)',
        help='Registros que se eligen al abrir el tablero, p. ej. [("is_current", "=", True)] '
             'para la semana vigente. Vacío = sin filtro.')
    # Selección
    selection_model_id = fields.Many2one('ir.model', string='Modelo del campo de selección', ondelete='cascade')
    default_selection = fields.Char(string='Valores por omisión', help='Valores técnicos separados por coma.')
    # Fecha
    default_period = fields.Selection(DATE_PRESETS, string='Periodo por omisión', default='this_year')
    required = fields.Boolean(string='Obligatorio', help='No se puede dejar vacío (p. ej. la semana).')

    @api.constrains('record_domain', 'default_domain')
    def _check_domains(self):
        for flt in self:
            for domain in (flt.record_domain, flt.default_domain):
                if domain:
                    try:
                        safe_eval(domain)
                    except Exception as error:
                        raise ValidationError(_('Dominio inválido en el filtro %(name)s: %(error)s',
                                                name=flt.name, error=error)) from error

    def _default_value(self):
        self.ensure_one()
        if self.filter_type == 'date':
            return self._normalize_value({'preset': self.default_period or 'all'})
        if self.filter_type == 'many2one':
            if not self.default_domain or not self.comodel_name:
                return []
            records = self.env[self.comodel_name].sudo(False).search(safe_eval(self.default_domain),
                                                                     limit=None if self.multiple else 1)
            return records.ids
        if self.filter_type == 'selection':
            return [v.strip() for v in (self.default_selection or '').split(',') if v.strip()]
        return ''

    def _normalize_value(self, value):
        """Convierte el valor que llega de la pantalla al formato interno."""
        self.ensure_one()
        if self.filter_type == 'date':
            value = value or {}
            preset = value.get('preset') or 'all'
            date_from, date_to = self._period_range(preset, value.get('from'), value.get('to'))
            return {'preset': preset, 'from': date_from, 'to': date_to}
        if self.filter_type == 'many2one':
            ids = [int(v) for v in (value or [])]
            if not ids and self.required:      # p. ej. la semana: nunca vacío
                return self._default_value()
            return ids if self.multiple else ids[:1]
        if self.filter_type == 'selection':
            return list(value or [])
        return (value or '').strip()

    def _period_range(self, preset, date_from=None, date_to=None):
        """Fechas inicial y final (incluidas) de un periodo."""
        today = fields.Date.context_today(self)
        if preset == 'this_year':
            return date(today.year, 1, 1), date(today.year, 12, 31)
        if preset == 'last_year':
            return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
        if preset == 'this_quarter':
            first_month = 3 * ((today.month - 1) // 3) + 1
            start = date(today.year, first_month, 1)
            return start, start + relativedelta(months=3, days=-1)
        if preset == 'this_month':
            return today.replace(day=1), today.replace(day=calendar.monthrange(today.year, today.month)[1])
        if preset == 'last_month':
            start = today.replace(day=1) - relativedelta(months=1)
            return start, today.replace(day=1) - timedelta(days=1)
        if preset == 'last_30':
            return today - timedelta(days=29), today
        if preset == 'last_12_months':
            return today.replace(day=1) - relativedelta(months=11), today
        if preset == 'custom':
            return (fields.Date.to_date(date_from) if date_from else None,
                    fields.Date.to_date(date_to) if date_to else None)
        return None, None

    def _payload(self, value):
        """Definición y valor actual del filtro para la interfaz."""
        self.ensure_one()
        data = {'id': self.id, 'name': self.name, 'type': self.filter_type,
                'required': self.required, 'multiple': self.multiple}
        if self.filter_type == 'date':
            data.update(presets=DATE_PRESETS, value={
                'preset': value['preset'],
                'from': fields.Date.to_string(value['from']) if value['from'] else False,
                'to': fields.Date.to_string(value['to']) if value['to'] else False,
            })
        elif self.filter_type == 'many2one':
            data.update(model=self.comodel_name, domain=safe_eval(self.record_domain or '[]'),
                        value=value)
        elif self.filter_type == 'selection':
            options = []
            model = self.selection_model_id.model
            if model and self.field_name and self.field_name in self.env[model]._fields:
                options = self.env[model]._fields[self.field_name]._description_selection(self.env)
            data.update(options=options, value=value)
        else:
            data.update(value=value)
        return data

    def _domain_for(self, field_path, value, model):
        """Condición de dominio de este filtro sobre un campo de un modelo."""
        self.ensure_one()
        if self.filter_type == 'date':
            if not value['from'] and not value['to']:
                return []
            field = _resolve_field(model, field_path)
            domain = []
            if field and field.type == 'datetime':
                if value['from']:
                    domain.append((field_path, '>=', datetime.combine(value['from'], time.min)))
                if value['to']:
                    domain.append((field_path, '<', datetime.combine(value['to'] + timedelta(days=1), time.min)))
            else:
                if value['from']:
                    domain.append((field_path, '>=', value['from']))
                if value['to']:
                    domain.append((field_path, '<=', value['to']))
            return domain
        if self.filter_type in ('many2one', 'selection'):
            return [(field_path, 'in', value)] if value else []
        return [(field_path, 'ilike', value)] if value else []


def _resolve_field(model, path):
    """Último campo de una ruta con puntos (p. ej. stage_id.report_close_on_enter)."""
    field = None
    for name in (path or '').split('.'):
        field = model._fields.get(name)
        if field is None:
            return None
        if field.relational:
            model = model.env[field.comodel_name]
    return field


# ======================================================================
# Elemento
# ======================================================================
class BusinessDashboardWidget(models.Model):
    _name = 'business.dashboard.widget'
    _description = 'Elemento de tablero'
    _order = 'sequence, id'

    dashboard_id = fields.Many2one('business.dashboard', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Título', required=True, translate=True)
    subtitle = fields.Char(string='Nota', translate=True, help='Texto chico bajo el título o el valor.')
    code = fields.Char(string='Código', help='Nombre corto para usar el valor de un indicador en fórmulas '
                                              '(solo letras, números y guion bajo).')
    widget_type = fields.Selection(WIDGET_TYPES, string='Tipo', required=True, default='kpi')
    width = fields.Selection(WIDTHS, string='Ancho', default='6', required=True)
    height = fields.Integer(string='Alto (px)', default=320, help='Para gráficas, tablas y listados.')
    hidden = fields.Boolean(string='Oculto', help='No se muestra; sirve solo para usarlo en fórmulas.')

    # ---------------- Origen de los datos ----------------
    model_id = fields.Many2one('ir.model', string='Modelo', ondelete='cascade')
    model_name = fields.Char(related='model_id.model', string='Modelo (técnico)')
    domain = fields.Char(string='Dominio', default='[]', help='Registros que se toman en cuenta.')
    groupby_field_id = fields.Many2one(
        'ir.model.fields', string='Agrupar por', ondelete='set null',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', %s)]" % (GROUPABLE_TYPES,))
    groupby_interval = fields.Selection(INTERVALS, string='Intervalo', default='month')
    groupby2_field_id = fields.Many2one(
        'ir.model.fields', string='Series por (gráfica)', ondelete='set null',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', %s)]" % (GROUPABLE_TYPES,),
        help='Gráficas: una serie por cada valor de este campo (usa la primera medida).')
    groupby2_interval = fields.Selection(INTERVALS, string='Intervalo (series)', default='month')
    range_field_id = fields.Many2one(
        'ir.model.fields', string='Rangos de antigüedad desde', ondelete='set null',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ('date', 'datetime'))]",
        help='Agrupa por días transcurridos desde esta fecha hasta hoy (en lugar de "Agrupar por").')
    range_bounds = fields.Char(string='Rangos (días)', default='30,60,90,180',
                               help='Límites de los rangos separados por coma. 30,60,90,180 = 0–30, 31–60, '
                                    '61–90, 91–180 y más de 180 días.')
    sort_mode = fields.Selection(SORT_MODES, string='Orden', default='group')
    limit = fields.Integer(string='Máximo de renglones', default=0, help='0 = sin límite.')
    measure_ids = fields.One2many('business.dashboard.measure', 'widget_id', string='Medidas', copy=True)
    filter_map_ids = fields.One2many('business.dashboard.widget.filter', 'widget_id',
                                     string='Filtros aplicados', copy=True)

    # ---------------- Indicador ----------------
    formula = fields.Char(string='Fórmula', help='Indicador calculado con otros indicadores, p. ej. '
                                                 'div(ganados, ganados + perdidos).')
    value_format = fields.Selection(VALUE_FORMATS, string='Formato', default='number')
    abbreviate = fields.Boolean(string='Abreviar (k, M)', default=True)
    color_mode = fields.Selection(COLOR_MODES, string='Color', default='none')
    threshold = fields.Char(string='Umbral', help='Número o fórmula, p. ej. 0.15 o alerta_margen.')
    color = fields.Char(string='Color de fondo', default='#F9FAFB')
    secondary_code = fields.Char(
        string='Segundo valor', help='Código de otro indicador que se muestra junto al valor, p. ej. el monto: '
                                     '"16 · $362.5 M".')

    # ---------------- Gráfica ----------------
    chart_type = fields.Selection(CHART_TYPES, string='Tipo de gráfica', default='bar')
    show_legend = fields.Boolean(string='Mostrar leyenda', default=True)
    show_values = fields.Boolean(string='Números sobre las barras')

    # ---------------- Tabla ----------------
    show_total = fields.Boolean(string='Renglón de total', default=True)
    total_first = fields.Boolean(string='Total arriba')
    row_label = fields.Char(string='Encabezado de renglones', translate=True)
    table_transpose = fields.Boolean(
        string='Grupos en columnas',
        help='Cada grupo (p. ej. cada mes) es una columna y cada medida un renglón; el total es la última '
             'columna.')

    # ---------------- Listado ----------------
    list_fields = fields.Char(string='Columnas', help='Campos separados por coma, p. ej. '
                                                     'date_closed, partner_id, name, expected_revenue. Para cambiar '
                                                     'el encabezado: campo:Etiqueta, p. ej. date_closed:Cierre.')
    list_order = fields.Char(string='Orden del listado', help='P. ej. expected_revenue desc.')
    list_show_number = fields.Boolean(string='Numerar renglones (#)')
    list_show_total = fields.Boolean(string='Renglón de total', help='Suma las columnas numéricas de todos los '
                                                                      'registros (no solo los que se muestran).')
    list_highlight = fields.Char(string='Resaltar en rojo', help='Regla "campo > número", p. ej. '
                                                               'report_age_days > 365.')
    list_group_field = fields.Char(string='Agrupar listado por', help='Campo, p. ej. stage_id: un encabezado '
                                                                     'por cada valor con su cuenta.')

    # ---------------- Detalle ----------------
    drilldown_view_id = fields.Many2one('ir.ui.view', string='Formulario al abrir un registro',
                                        domain="[('type', '=', 'form'), ('model', '=', model_name)]")

    # Vista previa en la configuración
    preview = fields.Text(string='Vista previa', compute='_compute_preview')

    _code_uniq = models.Constraint('UNIQUE(dashboard_id, code)', 'El código ya se usa en este tablero.')

    # ------------------------------------------------------------------
    # Validaciones y vista previa
    # ------------------------------------------------------------------
    @api.constrains('domain', 'model_id', 'formula', 'code', 'list_fields', 'widget_type', 'range_bounds',
                    'range_field_id', 'list_highlight', 'list_group_field')
    def _check_config(self):
        for widget in self:
            if widget.range_field_id:
                widget._range_bounds()
            if widget.code and not widget.code.replace('_', '').isalnum():
                raise ValidationError(_('El código "%s" solo puede tener letras, números y guion bajo.', widget.code))
            if widget.widget_type in ('chart', 'table', 'list') or (
                    widget.widget_type == 'kpi' and not widget.formula):
                if not widget.model_id:
                    raise ValidationError(_('El elemento "%s" necesita un modelo.', widget.name))
            if widget.model_id and widget.domain:
                widget._check_domain(widget.domain)
            if widget.widget_type == 'kpi' and not widget.code:
                raise ValidationError(_('El indicador "%s" necesita un código.', widget.name))
            if widget.widget_type == 'list' and widget.model_id:
                model = self.env[widget.model_name]
                if widget.list_highlight:
                    rule = HIGHLIGHT_RULE.match(widget.list_highlight)
                    if not rule or rule.group(1) not in model._fields:
                        raise ValidationError(_('La regla para resaltar de "%s" debe ser "campo > número", p. ej. '
                                                'report_age_days > 365.', widget.name))
                if widget.list_group_field and widget.list_group_field not in model._fields:
                    raise ValidationError(_('El campo "%(field)s" no existe en %(model)s.',
                                            field=widget.list_group_field, model=widget.model_id.name))
                for name in widget._list_field_names():
                    if name not in model._fields:
                        raise ValidationError(_('El campo "%(field)s" no existe en %(model)s.',
                                                field=name, model=widget.model_id.name))

    def _check_domain(self, domain):
        try:
            self.env[self.model_name].search_count(self._eval_domain(domain), limit=1)
        except Exception as error:
            raise ValidationError(_('Dominio inválido en "%(name)s": %(error)s', name=self.name, error=error)) from error

    @api.depends('widget_type', 'model_id', 'domain', 'formula', 'measure_ids', 'groupby_field_id')
    def _compute_preview(self):
        for widget in self:
            if not widget.dashboard_id or not widget.id or widget.widget_type == 'section':
                widget.preview = False
                continue
            try:
                data = widget.dashboard_id.get_dashboard_data()
                item = next((w for w in data['widgets'] if w['id'] == widget.id), None)
                if item is None:
                    widget.preview = _('Elemento oculto (solo para fórmulas).')
                elif item['error']:
                    widget.preview = _('Error: %s', item['error'])
                elif widget.widget_type == 'kpi':
                    widget.preview = _('Valor con los filtros por omisión: %s', item['display'])
                elif widget.widget_type == 'chart':
                    widget.preview = _('%(labels)s grupos, %(series)s series',
                                       labels=len(item['labels']), series=len(item['datasets']))
                elif widget.widget_type == 'table':
                    widget.preview = _('%s renglones', len(item['rows']))
                else:
                    widget.preview = _('%s registros', len(item['records']))
            except Exception as error:  # noqa: BLE001
                widget.preview = _('Error: %s', error)

    # ------------------------------------------------------------------
    # Dominio con filtros
    # ------------------------------------------------------------------
    def _eval_domain(self, text):
        """Dominio escrito como texto. Acepta fechas relativas con context_today() y relativedelta."""
        today = fields.Date.context_today(self)
        return list(safe_eval(text or '[]', {'context_today': lambda: today, 'relativedelta': relativedelta}))

    def _filter_field(self, flt, period_field=None):
        """Campo al que se aplica un filtro en este elemento (None = no se aplica)."""
        mapping = self.filter_map_ids.filtered(lambda m: m.filter_id == flt)
        if mapping:
            return mapping[0].field_path or None
        if flt.filter_type == 'date' and period_field:
            return period_field
        model = self.env[self.model_name]
        if flt.field_name and _resolve_field(model, flt.field_name):
            return flt.field_name
        return None

    def _full_domain(self, filter_values, extra_domain=None, period_field=None):
        self.ensure_one()
        model = self.env[self.model_name]
        domain = self._eval_domain(self.domain)
        if extra_domain:
            domain += self._eval_domain(extra_domain)
        for flt in self.dashboard_id.filter_ids:
            path = self._filter_field(flt, period_field)
            if path and _resolve_field(model, path):
                domain += flt._domain_for(path, filter_values.get(flt.id), model)
        return domain

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    def _is_formula_kpi(self):
        return bool(self.formula)

    def _measure_domain(self, measure, filter_values):
        """(modelo, dominio) de una medida.

        Medida del modelo del elemento: dominio del elemento + filtros.
        Medida de otro modelo (source_model_id): su dominio adicional + los
        filtros que ese modelo tenga; el periodo se aplica a su campo de
        fecha. Un filtro marcado "no aplicar" en el elemento tampoco se aplica
        a sus medidas de otro modelo.
        """
        if not measure.source_model_id:
            return (self.env[self.model_name],
                    self._full_domain(filter_values, measure.extra_domain, measure.period_field))
        model = self.env[measure.source_model_id.model]
        domain = self._eval_domain(measure.extra_domain)
        period_field = measure.period_field or measure.source_groupby_field
        for flt in self.dashboard_id.filter_ids:
            mapping = self.filter_map_ids.filtered(lambda m, flt=flt: m.filter_id == flt)
            if mapping and not mapping[0].field_path:
                continue
            path = period_field if flt.filter_type == 'date' else flt.field_name
            if path and _resolve_field(model, path):
                domain += flt._domain_for(path, filter_values.get(flt.id), model)
        return model, domain

    def _measure_value(self, measure, filter_values, groupby=(), extra_domain=None):
        """Valor de una medida (o por grupo) con _read_group."""
        model, domain = self._measure_domain(measure, filter_values)
        if extra_domain:
            domain = domain + list(extra_domain)
        aggregate = measure._aggregate_spec()
        return model.sudo(False)._read_group(domain, list(groupby), [aggregate])

    # ---------------- Rangos de antigüedad ----------------
    def _range_bounds(self):
        try:
            bounds = sorted({int(b) for b in (self.range_bounds or '').split(',') if b.strip()})
        except ValueError as error:
            raise ValidationError(_('Los rangos de "%s" deben ser números de días separados por coma, '
                                    'p. ej. 30,60,90,180.', self.name)) from error
        if not bounds or bounds[0] <= 0:
            raise ValidationError(_('Los rangos de "%s" deben ser números de días mayores a cero.', self.name))
        return bounds

    def _range_buckets(self):
        """[(llave, etiqueta, dominio)] de cada rango, del más reciente al más antiguo."""
        field = self.range_field_id
        today = fields.Date.context_today(self)

        def limit(days):
            day = today - timedelta(days=days)
            return datetime.combine(day, time.min) if field.ttype == 'datetime' else day

        buckets, previous = [], None
        for i, high in enumerate(self._range_bounds()):
            domain = [(field.name, '>=', limit(high))]
            if previous is None:
                label = _('0–%s días', high)
            else:
                domain.append((field.name, '<', limit(previous)))
                label = _('%(low)s–%(high)s días', low=previous + 1, high=high)
            buckets.append(('r%s' % i, label, domain))
            previous = high
        buckets.append(('r%s' % len(buckets), _('Más de %s días', previous),
                        [(field.name, '<', limit(previous))]))
        return buckets

    def _compute_kpi_value(self, filter_values, kpi_values):
        self.ensure_one()
        if self.formula:
            return _safe_formula(self.formula, kpi_values)
        measure = self.measure_ids[:1]
        if not measure:
            return 0.0
        [(value,)] = self._measure_value(measure, filter_values)
        return value or 0.0

    def _threshold_value(self, kpi_values):
        if not self.threshold:
            return None
        return _safe_formula(self.threshold, kpi_values)

    def _kpi_payload(self, kpi_values, kpi_widgets):
        value = kpi_values.get(self.code, 0.0)
        secondary = kpi_widgets.get(self.secondary_code) if self.secondary_code else None
        return {
            'value': value,
            'display': self._format(value),
            'format': self.value_format, 'abbreviate': self.abbreviate,
            'color': self.color or '#F9FAFB',
            'state': _color_state(self.color_mode, value, self._threshold_value(kpi_values)),
            'drilldown': bool(self.model_id and not self.formula),
            'secondary': secondary._short(kpi_values.get(secondary.code)) if secondary else False,
        }

    def _short(self, value):
        return _short_number(value, self.value_format, self.abbreviate, self.env.company.currency_id.symbol)

    def _render_text(self, text, kpi_values, kpi_widgets):
        """Cambia {código} por el valor (corto) del indicador con ese código."""
        def replace(match):
            code = match.group(1)
            if code not in kpi_values:
                return match.group(0)
            widget = kpi_widgets.get(code)
            return widget._short(kpi_values[code]) if widget else str(kpi_values[code])
        return PLACEHOLDER.sub(replace, text or '')

    def _format(self, value):
        if self.value_format == 'percent':
            return '%.2f %%' % ((value or 0.0) * 100)
        if self.value_format == 'integer':
            return '{:,.0f}'.format(value or 0)
        if self.value_format == 'number1':
            return '{:,.1f}'.format(value or 0.0)
        symbol = self.env.company.currency_id.symbol if self.value_format == 'monetary' else ''
        return '%s%s' % (symbol, '{:,.2f}'.format(value or 0.0))

    # ---------------- Agrupación ----------------
    def _groupby_spec(self, field, interval):
        if not field:
            return None
        if field.ttype in ('date', 'datetime'):
            return '%s:%s' % (field.name, interval or 'month')
        return field.name

    def _group_key_label(self, field, interval, value, model_name=None):
        """(llave, etiqueta, orden) de un valor agrupado."""
        if field.ttype == 'many2one':
            return (value.id or False, value.display_name if value else _('Sin definir'), value.display_name or '')
        if field.ttype == 'selection':
            selection = self.env[model_name or self.model_name]._fields[field.name]._description_selection(self.env)
            labels = dict(selection)
            keys = [k for k, _l in selection]
            return (value, labels.get(value, _('Sin definir')), keys.index(value) if value in keys else 999)
        if field.ttype in ('date', 'datetime'):
            if not value:
                return (False, _('Sin fecha'), date.min)
            day = value.date() if isinstance(value, datetime) else value
            if interval == 'year':
                label = str(day.year)
            elif interval == 'quarter':
                label = 'T%s %s' % ((day.month - 1) // 3 + 1, day.year)
            elif interval == 'month':
                label = format_date(self.env, day, date_format='MMM yyyy')
            elif interval == 'week':
                label = 'S%s %s' % (day.isocalendar()[1], day.isocalendar()[0])
            else:
                label = format_date(self.env, day, date_format='dd/MM/yyyy')
            return (fields.Date.to_string(day), label, day)
        if field.ttype == 'boolean':
            return (value, _('Sí') if value else _('No'), not value)
        return (value, str(value) if value not in (False, None) else _('Sin definir'), value or '')

    @staticmethod
    def _source_field(measure):
        """Campo de agrupación de una medida de otro modelo (nombre y tipo)."""
        model_field = measure.env[measure.source_model_id.model]._fields.get(measure.source_groupby_field or '')
        if not model_field:
            return None
        return SimpleNamespace(name=model_field.name, ttype=model_field.type)

    def _grouped(self, filter_values):
        """Valores agrupados de cada medida de datos: {código: {llave: valor}} y grupos ordenados."""
        if self.range_field_id:
            return self._grouped_ranges(filter_values)
        field, interval = self.groupby_field_id, self.groupby_interval
        spec = self._groupby_spec(field, interval)
        groups, data = {}, {}
        for measure in self.measure_ids.filtered(lambda m: not m.formula):
            data[measure.code] = {}
            measure_field, model_name = field, None
            if measure.source_model_id:
                # Medida de otro modelo: se agrupa por su propio campo (p. ej. el mes de la meta)
                measure_field, model_name = self._source_field(measure), measure.source_model_id.model
                measure_spec = self._groupby_spec(measure_field, interval) if spec and measure_field else None
                if spec and not measure_spec:
                    continue
            else:
                measure_spec = spec
            if measure_spec:
                rows = self._measure_value(measure, filter_values, [measure_spec])
            else:   # sin agrupación: un solo renglón
                rows = [(None, self._measure_value(measure, filter_values)[0][0])]
            for value, amount in rows:
                key, label, order = self._group_key_label(measure_field, interval, value, model_name) \
                    if measure_spec else ('total', '', 0)
                groups.setdefault(key, (label, order))
                data[measure.code][key] = amount or 0.0
        keys = list(groups)
        first = self.measure_ids[:1]
        if self.sort_mode in ('value_desc', 'value_asc') and first:
            keys.sort(key=lambda k: data.get(first.code, {}).get(k, 0.0), reverse=self.sort_mode == 'value_desc')
        else:
            keys.sort(key=lambda k: (str(type(groups[k][1])), groups[k][1]))
        if self.limit:
            keys = keys[:self.limit]
        return keys, groups, data

    def _grouped_ranges(self, filter_values):
        """Como _grouped, pero un grupo por rango de antigüedad (siempre en orden)."""
        buckets = self._range_buckets()
        groups = {key: (label, i) for i, (key, label, _domain) in enumerate(buckets)}
        data = {}
        for measure in self.measure_ids.filtered(lambda m: not m.formula):
            data[measure.code] = {}
            if measure.source_model_id:     # los rangos son del modelo del elemento
                continue
            for key, _label, domain in buckets:
                [(value,)] = self._measure_value(measure, filter_values, extra_domain=domain)
                data[measure.code][key] = value or 0.0
        return [key for key, _label, _domain in buckets], groups, data

    def _chart_payload(self, filter_values):
        palette = ['#2F5BEA', '#E8556F', '#F59E0B', '#10B981', '#8B5CF6', '#06B6D4', '#6B7280', '#EC4899']
        if self.groupby2_field_id and self.measure_ids and not self.range_field_id:
            # Series por un segundo campo, con la primera medida
            measure = self.measure_ids[0]
            spec1 = self._groupby_spec(self.groupby_field_id, self.groupby_interval)
            spec2 = self._groupby_spec(self.groupby2_field_id, self.groupby2_interval)
            rows = self._measure_value(measure, filter_values, [spec1, spec2])
            labels, series, values = {}, {}, {}
            for value1, value2, amount in rows:
                k1, l1, o1 = self._group_key_label(self.groupby_field_id, self.groupby_interval, value1)
                k2, l2, o2 = self._group_key_label(self.groupby2_field_id, self.groupby2_interval, value2)
                labels.setdefault(k1, (l1, o1))
                series.setdefault(k2, (l2, o2))
                values[(k1, k2)] = amount or 0.0
            keys1 = sorted(labels, key=lambda k: (str(type(labels[k][1])), labels[k][1]))
            keys2 = sorted(series, key=lambda k: (str(type(series[k][1])), series[k][1]))
            datasets = [{'label': series[k2][0], 'data': [values.get((k1, k2), 0.0) for k1 in keys1],
                         'color': palette[i % len(palette)], 'measure_id': measure.id, 'group2': k2}
                        for i, k2 in enumerate(keys2)]
            return {'chart_type': self.chart_type, 'labels': [labels[k][0] for k in keys1],
                    'keys': keys1, 'datasets': datasets, 'legend': self.show_legend, 'show_values': self.show_values,
                    'format': measure.value_format}
        keys, groups, data = self._grouped(filter_values)
        datasets = []
        for i, measure in enumerate(self.measure_ids.filtered(lambda m: not m.hidden)):
            if measure.formula:
                series = [_safe_formula(measure.formula, {c: data[c].get(k, 0.0) for c in data}) for k in keys]
            else:
                series = [data[measure.code].get(k, 0.0) for k in keys]
            datasets.append({'label': measure.name, 'data': series, 'measure_id': measure.id,
                             'color': measure.color or palette[i % len(palette)],
                             # Gráficas combinadas: barra o línea y eje derecho por medida
                             'series_type': measure.series_type or False, 'right_axis': measure.right_axis,
                             'format': measure.value_format or 'number'})
        right = next((d for d in datasets if d['right_axis']), None)
        return {'chart_type': self.chart_type, 'labels': [groups[k][0] for k in keys], 'keys': keys,
                'datasets': datasets, 'legend': self.show_legend, 'show_values': self.show_values,
                'format': next((d['format'] for d in datasets if not d['right_axis']), 'number'),
                'right_format': right['format'] if right else False}

    def _table_payload(self, filter_values, kpi_values):
        keys, groups, data = self._grouped(filter_values)
        measures = self.measure_ids
        rows = []

        def build_row(key, label, raw):
            row_values = {}
            for measure in measures:      # en orden: las fórmulas pueden usar columnas anteriores
                if measure.formula:
                    names = dict(kpi_values)
                    names.update(row_values)
                    names.update({c: v for c, v in raw.items() if c not in row_values})
                    row_values[measure.code] = _safe_formula(measure.formula, names)
                else:
                    row_values[measure.code] = raw.get(measure.code, 0.0)
            cells = []
            for measure in measures.filtered(lambda m: not m.hidden):
                value = row_values[measure.code]
                threshold = _safe_formula(measure.threshold, dict(kpi_values, **row_values)) \
                    if measure.threshold else None
                cells.append({'value': value, 'state': _color_state(measure.color_mode, value, threshold),
                              'format': measure.value_format,
                              'click': {'group_key': key, 'measure_id': measure.id}})
            return {'key': key, 'label': label, 'cells': cells, 'click': {'group_key': key}}

        for key in keys:
            rows.append(build_row(key, groups[key][0], {c: data[c].get(key, 0.0) for c in data}))
        total = None
        if self.show_total and (self.groupby_field_id or self.range_field_id):
            raw_total = {}
            for measure in measures.filtered(lambda m: not m.formula):
                if measure.aggregate in ('sum', 'count'):
                    raw_total[measure.code] = sum(data[measure.code].get(k, 0.0) for k in keys)
                else:
                    [(value,)] = self._measure_value(measure, filter_values)
                    raw_total[measure.code] = value or 0.0
            total = build_row('__total__', _('Total'), raw_total)
        if self.table_transpose:
            return self._transposed_payload(rows, total)
        return {
            'row_label': self.row_label or (self.groupby_field_id.field_description or ''),
            'columns': [{'id': m.id, 'name': m.name, 'format': m.value_format}
                        for m in measures.filtered(lambda m: not m.hidden)],
            'rows': rows, 'total': total, 'total_first': self.total_first,
            'drilldown': True,
        }

    def _transposed_payload(self, rows, total):
        """Tabla con los grupos en columnas: un renglón por medida visible."""
        visible = self.measure_ids.filtered(lambda m: not m.hidden)
        source_rows = list(rows)
        if total:
            source_rows = [total] + source_rows if self.total_first else source_rows + [total]
        columns = [{'id': row['key'], 'name': row['label'], 'total': row['key'] == '__total__'}
                   for row in source_rows]
        out_rows = []
        for index, measure in enumerate(visible):
            out_rows.append({
                'key': measure.code, 'label': measure.name, 'format': measure.value_format,
                'click': {'measure_id': measure.id},
                'cells': [dict(row['cells'][index], total=row['key'] == '__total__') for row in source_rows],
            })
        return {
            'row_label': self.row_label or '',
            'columns': columns, 'rows': out_rows, 'total': None, 'total_first': False,
            'transposed': True, 'drilldown': True,
        }

    def _list_columns_spec(self):
        """[(campo, etiqueta o None)] de "Columnas" (campo o campo:Etiqueta)."""
        spec = []
        for part in (self.list_fields or '').split(','):
            name, _sep, label = part.partition(':')
            if name.strip():
                spec.append((name.strip(), label.strip() or None))
        return spec

    def _list_field_names(self):
        return [name for name, _label in self._list_columns_spec()]

    def _list_payload(self, filter_values):
        model = self.env[self.model_name].sudo(False)
        names = self._list_field_names() or ['display_name']
        domain = self._full_domain(filter_values)
        group_name = self.list_group_field if self.list_group_field in model._fields else False
        order = self.list_order or None
        if group_name:      # agrupado: primero por el campo (en el orden de su modelo), luego el orden indicado
            order = ', '.join(part for part in (group_name, self.list_order) if part)
        read_names = names + ([group_name] if group_name and group_name not in names else [])
        records = model.search_read(domain, read_names, order=order, limit=self.limit or 15)
        labels = dict(self._list_columns_spec())
        columns = []
        for name in names:
            field = model._fields[name]
            column = {'name': name, 'label': labels.get(name) or field.get_description(self.env)['string'],
                      'type': field.type}
            if field.type == 'float' and isinstance(field.get_digits(self.env), tuple):
                column['digits'] = field.get_digits(self.env)[1]
            columns.append(column)
        rule = HIGHLIGHT_RULE.match(self.list_highlight or '')
        compare = {'>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
                   '<': lambda a, b: a < b, '<=': lambda a, b: a <= b}

        def cell_text(name, kind, value):
            if isinstance(value, (list, tuple)) and len(value) == 2 and kind == 'many2one':
                return value[1]
            if kind == 'selection':
                return dict(model._fields[name]._description_selection(self.env)).get(value, value)
            if kind in ('date', 'datetime') and value:
                return format_date(self.env, value)
            return value

        rows, group_rows, last_group = [], {}, object()
        for number, record in enumerate(records, start=1):
            if group_name and record[group_name] != last_group:
                last_group = record[group_name]
                label = cell_text(group_name, model._fields[group_name].type, last_group) or _('Sin definir')
                group_rows[len(rows)] = {'id': 'group-%s' % len(rows), 'group': label, 'count': 0}
                rows.append(group_rows[len(rows)])
            if group_name:
                rows[max(group_rows)]['count'] += 1
            cells = []
            for column in columns:
                value = cell_text(column['name'], column['type'], record.get(column['name']))
                cells.append(value if value not in (False, None) else '')
            red = []
            if rule:
                field_value = record.get(rule.group(1))
                if field_value is not None and field_value is not False and \
                        compare[rule.group(2)](field_value, float(rule.group(3))):
                    red = [i for i, column in enumerate(columns) if column['name'] == rule.group(1)] or \
                        list(range(len(columns)))
            rows.append({'id': record['id'], 'number': number, 'cells': cells, 'red': red})
        # Total y cuenta de TODOS los registros del dominio (no solo los que se muestran)
        count = model.search_count(domain)
        total = False
        if self.list_show_total:
            numeric = [c['name'] for c in columns
                       if c['type'] in NUMERIC_TYPES and model._fields[c['name']].store
                       and model._fields[c['name']].aggregator == 'sum']
            sums = dict(zip(numeric, model._read_group(domain, [], ['%s:sum' % n for n in numeric])[0])) \
                if numeric else {}
            total = [sums.get(c['name'], '') if c['name'] in sums else '' for c in columns]
        return {'columns': columns, 'records': rows, 'model': self.model_name, 'count': count,
                'shown': len(records), 'total': total, 'show_number': self.list_show_number,
                'grouped': bool(group_name)}

    # ------------------------------------------------------------------
    # Detalle (clic en un valor, barra o renglón)
    # ------------------------------------------------------------------
    def get_drilldown_action(self, filter_values=None, group_key=None, measure_id=None, group2_key=None):
        """Acción con los registros que forman un valor."""
        self.ensure_one()
        self.dashboard_id.check_access('read')
        self = self.sudo()  # noqa: PLW0642 - configuración; la acción abre los datos con los permisos del usuario
        values = self.dashboard_id._resolve_filter_values(filter_values or {})
        measure = self.env['business.dashboard.measure'].browse(measure_id) if measure_id else \
            self.measure_ids.filtered(lambda m: not m.formula)[:1]
        if measure and measure.formula:
            measure = self.measure_ids.filtered(lambda m: not m.formula and not m.source_model_id)[:1]
        grouped = group_key not in (None, '__total__', 'total')
        if measure and measure.source_model_id:
            # Medida de otro modelo (p. ej. la meta mensual): abre sus registros
            model, domain = self._measure_domain(measure, values)
            source_field = self._source_field(measure)
            if grouped and source_field and not self.range_field_id:
                domain += self._group_domain(source_field, self.groupby_interval, group_key)
            return {
                'type': 'ir.actions.act_window', 'name': '%s · %s' % (self.name, measure.name),
                'res_model': model._name, 'views': [(False, 'list'), (False, 'form')],
                'domain': domain, 'context': {'create': False}, 'target': 'current',
            }
        domain = self._full_domain(values, measure.extra_domain if measure else None,
                                   measure.period_field if measure else None)
        if grouped and self.range_field_id:
            domain += dict((key, dom) for key, _label, dom in self._range_buckets()).get(group_key, [])
        elif grouped and self.groupby_field_id:
            domain += self._group_domain(self.groupby_field_id, self.groupby_interval, group_key)
        if group2_key is not None and self.groupby2_field_id:
            domain += self._group_domain(self.groupby2_field_id, self.groupby2_interval, group2_key)
        context = {'create': False}
        if self.drilldown_view_id:
            context['form_view_ref'] = self.drilldown_view_id.xml_id or False
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self.model_name,
            'views': [(False, 'list'), (self.drilldown_view_id.id or False, 'form')],
            'domain': domain,
            'context': context,
            'target': 'current',
        }

    def get_record_action(self, res_id):
        """Abre un registro de un listado."""
        self.ensure_one()
        self.dashboard_id.check_access('read')
        self = self.sudo()  # noqa: PLW0642
        return {
            'type': 'ir.actions.act_window', 'res_model': self.model_name, 'res_id': res_id,
            'views': [(self.drilldown_view_id.id or False, 'form')], 'target': 'current',
        }

    @staticmethod
    def _group_domain(field, interval, key):
        if field.ttype in ('date', 'datetime') and key:
            start = fields.Date.to_date(key)
            end = start + {'day': relativedelta(days=1), 'week': relativedelta(weeks=1),
                           'month': relativedelta(months=1), 'quarter': relativedelta(months=3),
                           'year': relativedelta(years=1)}[interval or 'month']
            if field.ttype == 'datetime':
                start, end = datetime.combine(start, time.min), datetime.combine(end, time.min)
            return [(field.name, '>=', start), (field.name, '<', end)]
        return [(field.name, '=', key)]

    def action_edit(self):
        """Abre el elemento en su formulario de configuración."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'views': [(False, 'form')], 'target': 'new'}


def _color_state(mode, value, threshold):
    """'good' / 'bad' / False según la regla de color."""
    if mode == 'sign':
        return 'good' if (value or 0.0) >= 0 else 'bad'
    if mode == 'threshold' and threshold is not None:
        return 'bad' if (value or 0.0) < threshold else 'good'
    return False


# ======================================================================
# Medida
# ======================================================================
class BusinessDashboardMeasure(models.Model):
    _name = 'business.dashboard.measure'
    _description = 'Medida de un elemento de tablero'
    _order = 'sequence, id'

    widget_id = fields.Many2one('business.dashboard.widget', required=True, ondelete='cascade', index=True)
    model_id = fields.Many2one(related='widget_id.model_id')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Nombre', required=True, translate=True)
    code = fields.Char(string='Código', required=True,
                       help='Nombre corto para usar esta columna en fórmulas.')
    aggregate = fields.Selection(AGGREGATES, string='Cálculo', default='sum', required=True)
    # Medida de otro modelo (p. ej. Metas de venta mensuales en una gráfica de venta por mes)
    source_model_id = fields.Many2one(
        'ir.model', string='Datos de otro modelo', ondelete='cascade',
        help='Vacío = modelo del elemento. Si se elige otro modelo, la medida usa su dominio adicional y se '
             'alinea con los grupos del elemento por "Agrupar por (otro modelo)".')
    source_model_name = fields.Char(related='source_model_id.model', string='Otro modelo (técnico)')
    source_groupby_field = fields.Char(
        string='Agrupar por (otro modelo)',
        help='Campo del otro modelo equivalente al "Agrupar por" del elemento, p. ej. date para la meta '
             'mensual. También se usa para el filtro de periodo.')
    field_model_id = fields.Many2one('ir.model', compute='_compute_field_model_id')
    field_id = fields.Many2one(
        'ir.model.fields', string='Campo', ondelete='cascade',
        domain="[('model_id', '=', field_model_id), ('store', '=', True), ('ttype', 'in', %s)]" % (NUMERIC_TYPES,))
    series_type = fields.Selection(SERIES_TYPES, string='Dibujar como',
                                   help='Gráficas: vacío = según el tipo de gráfica.')
    right_axis = fields.Boolean(string='Eje derecho', help='Gráficas: usa un segundo eje a la derecha '
                                                           '(p. ej. monto junto a un conteo).')
    extra_domain = fields.Char(string='Dominio adicional', help='Solo para esta medida, p. ej. '
                                                                "[('won_status', '=', 'won')].")
    period_field = fields.Char(string='Campo de fecha para el periodo',
                               help='Si esta medida usa otro campo de fecha para el filtro de periodo.')
    formula = fields.Char(string='Fórmula', help='Calculada con otras columnas del renglón o con '
                                                 'indicadores, p. ej. div(diferencia, planeado).')
    value_format = fields.Selection(VALUE_FORMATS, string='Formato', default='number')
    color_mode = fields.Selection(COLOR_MODES, string='Color', default='none')
    threshold = fields.Char(string='Umbral', help='Número o fórmula (indicadores o columnas).')
    color = fields.Char(string='Color de la serie')
    hidden = fields.Boolean(string='Oculta', help='No se muestra; se usa en fórmulas.')

    _code_uniq = models.Constraint('UNIQUE(widget_id, code)', 'El código ya se usa en este elemento.')

    @api.depends('source_model_id', 'widget_id.model_id')
    def _compute_field_model_id(self):
        for measure in self:
            measure.field_model_id = measure.source_model_id or measure.widget_id.model_id

    @api.constrains('aggregate', 'field_id', 'formula', 'code', 'extra_domain', 'source_model_id',
                    'source_groupby_field')
    def _check_measure(self):
        for measure in self:
            if not measure.code.replace('_', '').isalnum():
                raise ValidationError(_('El código "%s" solo puede tener letras, números y guion bajo.', measure.code))
            if not measure.formula and measure.aggregate != 'count' and not measure.field_id:
                raise ValidationError(_('La medida "%s" necesita un campo, un conteo o una fórmula.', measure.name))
            if measure.source_model_id:
                model = self.env[measure.source_model_id.model]
                if measure.field_id and measure.field_id.model != model._name:
                    raise ValidationError(_('El campo de "%s" debe ser del otro modelo.', measure.name))
                if measure.source_groupby_field and measure.source_groupby_field not in model._fields:
                    raise ValidationError(_('El campo "%(field)s" no existe en %(model)s.',
                                            field=measure.source_groupby_field, model=measure.source_model_id.name))
                if measure.extra_domain:
                    try:
                        model.search_count(measure.widget_id._eval_domain(measure.extra_domain), limit=1)
                    except Exception as error:
                        raise ValidationError(_('Dominio inválido en "%(name)s": %(error)s',
                                                name=measure.name, error=error)) from error
            elif measure.extra_domain and measure.widget_id.model_id:
                measure.widget_id._check_domain(measure.extra_domain)

    def _aggregate_spec(self):
        if self.aggregate == 'count' or not self.field_id:
            return '__count'
        return '%s:%s' % (self.field_id.name, self.aggregate)


# ======================================================================
# Filtro aplicado a un elemento
# ======================================================================
class BusinessDashboardWidgetFilter(models.Model):
    _name = 'business.dashboard.widget.filter'
    _description = 'Filtro aplicado a un elemento'

    widget_id = fields.Many2one('business.dashboard.widget', required=True, ondelete='cascade', index=True)
    dashboard_id = fields.Many2one(related='widget_id.dashboard_id')
    filter_id = fields.Many2one('business.dashboard.filter', string='Filtro', required=True, ondelete='cascade',
                                domain="[('dashboard_id', '=', dashboard_id)]")
    field_path = fields.Char(string='Campo', help='Campo del modelo del elemento (se aceptan rutas con puntos). '
                                                  'Vacío = este filtro no se aplica al elemento.')

    _widget_filter_uniq = models.Constraint('UNIQUE(widget_id, filter_id)', 'El filtro ya está configurado.')
