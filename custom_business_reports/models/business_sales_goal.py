# -*- coding: utf-8 -*-
"""Metas de venta mensuales (19.0.8.0.0).

Un registro por mes y empresa con el monto que se espera vender. El tablero
"Seguimiento comercial" las usa en:

* Indicador "Meta de venta"  = Σ metas de los meses del periodo filtrado.
* Indicador "Avance vs meta" = venta ganada / meta.
* Gráfica "Venta por mes de cierre vs meta mensual" (barras de venta y la meta
  como línea).

Se capturan en CRM › Configuración › Metas de venta mensuales o en Tableros
DACSA › Configuración. La fecha siempre se guarda como el día 1 del mes.
"""
from odoo import _, api, fields, models
from odoo.tools import format_date


class BusinessSalesGoal(models.Model):
    _name = 'business.sales.goal'
    _description = 'Meta de venta mensual'
    _order = 'date desc, id desc'

    name = fields.Char(string='Meta', compute='_compute_name', store=True)
    date = fields.Date(string='Mes', required=True, index=True,
                       default=lambda self: fields.Date.context_today(self).replace(day=1),
                       help='Cualquier día del mes; se guarda como el día 1.')
    amount = fields.Monetary(string='Meta de venta', required=True, currency_field='currency_id')
    company_id = fields.Many2one('res.company', string='Empresa', required=True, index=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    note = fields.Char(string='Nota')

    _month_uniq = models.Constraint('UNIQUE(company_id, date)', 'Ya hay una meta para ese mes en la empresa.')

    @api.depends('date')
    def _compute_name(self):
        for goal in self:
            goal.name = _('Meta %s', format_date(self.env, goal.date, date_format='MMMM yyyy')) \
                if goal.date else _('Meta')

    @staticmethod
    def _first_day(vals):
        """Normaliza la fecha al día 1 del mes."""
        if vals.get('date'):
            vals['date'] = fields.Date.to_date(vals['date']).replace(day=1)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._first_day(dict(vals)) for vals in vals_list])

    def write(self, vals):
        return super().write(self._first_day(dict(vals)))
