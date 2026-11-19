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
"""
import calendar
import logging
from datetime import date, datetime, time, timedelta

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
VALUE_FORMATS = [('number', 'Número'), ('integer', 'Entero'), ('monetary', 'Moneda'), ('percent', 'Porcentaje')]
COLOR_MODES = [('none', 'Sin color'), ('sign', 'Verde si ≥ 0, rojo si < 0'),
               ('threshold', 'Rojo si es menor al umbral')]
SORT_MODES = [('group', 'Por agrupación'), ('value_desc', 'Mayor a menor (1a medida)'),
              ('value_asc', 'Menor a mayor (1a medida)')]
WIDTHS = [('3', '1/4'), ('4', '1/3'), ('6', '1/2'), ('8', '2/3'), ('9', '3/4'), ('12', 'Completo')]
NUMERIC_TYPES = ('integer', 'float', 'monetary')
GROUPABLE_TYPES = ('many2one', 'selection', 'date', 'datetime', 'char', 'boolean', 'integer')

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
        # 2) Datos de cada elemento visible
        for widget in self.widget_ids.filtered(lambda w: not w.hidden):
            data = {'id': widget.id, 'type': widget.widget_type, 'title': widget.name,
                    'subtitle': widget.subtitle or '', 'width': int(widget.width or 12),
                    'height': widget.height or 320, 'error': False}
            try:
                if widget.widget_type == 'kpi':
                    if widget.code in kpi_errors:
                        raise UserError(kpi_errors[widget.code])
                    data.update(widget._kpi_payload(kpi_values))
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
            'can_edit': self.env.user.has_group('custom_business_reports.group_dashboard_manager'),
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
            records = self.env[self.comodel_name].search(safe_eval(self.default_domain),
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

    # ---------------- Gráfica ----------------
    chart_type = fields.Selection(CHART_TYPES, string='Tipo de gráfica', default='bar')
    show_legend = fields.Boolean(string='Mostrar leyenda', default=True)

    # ---------------- Tabla ----------------
    show_total = fields.Boolean(string='Renglón de total', default=True)
    total_first = fields.Boolean(string='Total arriba')
    row_label = fields.Char(string='Encabezado de renglones', translate=True)

    # ---------------- Listado ----------------
    list_fields = fields.Char(string='Columnas', help='Campos separados por coma, p. ej. '
                                                     'date_closed, partner_id, name, expected_revenue.')
    list_order = fields.Char(string='Orden del listado', help='P. ej. expected_revenue desc.')

    # ---------------- Detalle ----------------
    drilldown_view_id = fields.Many2one('ir.ui.view', string='Formulario al abrir un registro',
                                        domain="[('type', '=', 'form'), ('model', '=', model_name)]")

    # Vista previa en la configuración
    preview = fields.Text(string='Vista previa', compute='_compute_preview')

    _code_uniq = models.Constraint('UNIQUE(dashboard_id, code)', 'El código ya se usa en este tablero.')

    # ------------------------------------------------------------------
    # Validaciones y vista previa
    # ------------------------------------------------------------------
    @api.constrains('domain', 'model_id', 'formula', 'code', 'list_fields', 'widget_type')
    def _check_config(self):
        for widget in self:
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
                for name in widget._list_field_names():
                    if name not in model._fields:
                        raise ValidationError(_('El campo "%(field)s" no existe en %(model)s.',
                                                field=name, model=widget.model_id.name))

    def _check_domain(self, domain):
        try:
            self.env[self.model_name].search_count(safe_eval(domain), limit=1)
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
        domain = list(safe_eval(self.domain or '[]'))
        if extra_domain:
            domain += list(safe_eval(extra_domain))
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

    def _measure_value(self, measure, filter_values, groupby=()):
        """Valor de una medida (o por grupo) con _read_group."""
        model = self.env[self.model_name]
        domain = self._full_domain(filter_values, measure.extra_domain, measure.period_field)
        aggregate = measure._aggregate_spec()
        return model._read_group(domain, list(groupby), [aggregate])

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

    def _kpi_payload(self, kpi_values):
        value = kpi_values.get(self.code, 0.0)
        return {
            'value': value,
            'display': self._format(value),
            'format': self.value_format, 'abbreviate': self.abbreviate,
            'color': self.color or '#F9FAFB',
            'state': _color_state(self.color_mode, value, self._threshold_value(kpi_values)),
            'drilldown': bool(self.model_id and not self.formula),
        }

    def _format(self, value):
        if self.value_format == 'percent':
            return '%.2f %%' % ((value or 0.0) * 100)
        if self.value_format == 'integer':
            return '{:,.0f}'.format(value or 0)
        symbol = self.env.company.currency_id.symbol if self.value_format == 'monetary' else ''
        return '%s%s' % (symbol, '{:,.2f}'.format(value or 0.0))

    # ---------------- Agrupación ----------------
    def _groupby_spec(self, field, interval):
        if not field:
            return None
        if field.ttype in ('date', 'datetime'):
            return '%s:%s' % (field.name, interval or 'month')
        return field.name

    def _group_key_label(self, field, interval, value):
        """(llave, etiqueta, orden) de un valor agrupado."""
        if field.ttype == 'many2one':
            return (value.id or False, value.display_name if value else _('Sin definir'), value.display_name or '')
        if field.ttype == 'selection':
            selection = self.env[self.model_name]._fields[field.name]._description_selection(self.env)
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

    def _grouped(self, filter_values):
        """Valores agrupados de cada medida de datos: {código: {llave: valor}} y grupos ordenados."""
        field, interval = self.groupby_field_id, self.groupby_interval
        spec = self._groupby_spec(field, interval)
        groups, data = {}, {}
        for measure in self.measure_ids.filtered(lambda m: not m.formula):
            data[measure.code] = {}
            if spec:
                rows = self._measure_value(measure, filter_values, [spec])
            else:   # sin agrupación: un solo renglón
                rows = [(None, self._measure_value(measure, filter_values)[0][0])]
            for value, amount in rows:
                key, label, order = self._group_key_label(field, interval, value) if spec else ('total', '', 0)
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

    def _chart_payload(self, filter_values):
        palette = ['#2F5BEA', '#E8556F', '#F59E0B', '#10B981', '#8B5CF6', '#06B6D4', '#6B7280', '#EC4899']
        if self.groupby2_field_id and self.measure_ids:
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
                    'keys': keys1, 'datasets': datasets, 'legend': self.show_legend,
                    'format': measure.value_format}
        keys, groups, data = self._grouped(filter_values)
        datasets = []
        for i, measure in enumerate(self.measure_ids.filtered(lambda m: not m.hidden)):
            if measure.formula:
                series = [_safe_formula(measure.formula, {c: data[c].get(k, 0.0) for c in data}) for k in keys]
            else:
                series = [data[measure.code].get(k, 0.0) for k in keys]
            datasets.append({'label': measure.name, 'data': series, 'measure_id': measure.id,
                             'color': measure.color or palette[i % len(palette)]})
        return {'chart_type': self.chart_type, 'labels': [groups[k][0] for k in keys], 'keys': keys,
                'datasets': datasets, 'legend': self.show_legend,
                'format': (self.measure_ids[:1].value_format or 'number')}

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
                cells.append({'value': value, 'state': _color_state(measure.color_mode, value, threshold)})
            return {'key': key, 'label': label, 'cells': cells}

        for key in keys:
            rows.append(build_row(key, groups[key][0], {c: data[c].get(key, 0.0) for c in data}))
        total = None
        if self.show_total and self.groupby_field_id:
            raw_total = {}
            for measure in measures.filtered(lambda m: not m.formula):
                if measure.aggregate in ('sum', 'count'):
                    raw_total[measure.code] = sum(data[measure.code].get(k, 0.0) for k in keys)
                else:
                    [(value,)] = self._measure_value(measure, filter_values)
                    raw_total[measure.code] = value or 0.0
            total = build_row('__total__', _('Total'), raw_total)
        return {
            'row_label': self.row_label or (self.groupby_field_id.field_description or ''),
            'columns': [{'id': m.id, 'name': m.name, 'format': m.value_format}
                        for m in measures.filtered(lambda m: not m.hidden)],
            'rows': rows, 'total': total, 'total_first': self.total_first,
            'drilldown': True,
        }

    def _list_field_names(self):
        return [name.strip() for name in (self.list_fields or '').split(',') if name.strip()]

    def _list_payload(self, filter_values):
        model = self.env[self.model_name]
        names = self._list_field_names() or ['display_name']
        records = model.search_read(self._full_domain(filter_values), names,
                                    order=self.list_order or None, limit=self.limit or 15)
        columns = []
        for name in names:
            field = model._fields[name]
            columns.append({'name': name, 'label': field.get_description(self.env)['string'],
                            'type': field.type})
        rows = []
        for record in records:
            cells = []
            for column in columns:
                value = record.get(column['name'])
                if isinstance(value, (list, tuple)) and len(value) == 2 and column['type'] == 'many2one':
                    value = value[1]
                elif column['type'] == 'selection':
                    value = dict(model._fields[column['name']]._description_selection(self.env)).get(value, value)
                elif column['type'] in ('date', 'datetime') and value:
                    value = format_date(self.env, value)
                cells.append(value if value not in (False, None) else '')
            rows.append({'id': record['id'], 'cells': cells})
        return {'columns': columns, 'records': rows, 'model': self.model_name}

    # ------------------------------------------------------------------
    # Detalle (clic en un valor, barra o renglón)
    # ------------------------------------------------------------------
    def get_drilldown_action(self, filter_values=None, group_key=None, measure_id=None, group2_key=None):
        """Acción con los registros que forman un valor."""
        self.ensure_one()
        values = self.dashboard_id._resolve_filter_values(filter_values or {})
        measure = self.env['business.dashboard.measure'].browse(measure_id) if measure_id else \
            self.measure_ids.filtered(lambda m: not m.formula)[:1]
        if measure and measure.formula:
            measure = self.measure_ids.filtered(lambda m: not m.formula)[:1]
        domain = self._full_domain(values, measure.extra_domain if measure else None,
                                   measure.period_field if measure else None)
        if group_key not in (None, '__total__', 'total') and self.groupby_field_id:
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
    field_id = fields.Many2one(
        'ir.model.fields', string='Campo', ondelete='cascade',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', %s)]" % (NUMERIC_TYPES,))
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

    @api.constrains('aggregate', 'field_id', 'formula', 'code', 'extra_domain')
    def _check_measure(self):
        for measure in self:
            if not measure.code.replace('_', '').isalnum():
                raise ValidationError(_('El código "%s" solo puede tener letras, números y guion bajo.', measure.code))
            if not measure.formula and measure.aggregate != 'count' and not measure.field_id:
                raise ValidationError(_('La medida "%s" necesita un campo, un conteo o una fórmula.', measure.name))
            if measure.extra_domain and measure.widget_id.model_id:
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
