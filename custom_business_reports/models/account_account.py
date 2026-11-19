# -*- coding: utf-8 -*-
"""Etapa 4: cuentas de anticipo de clientes.

Los apuntes de estas cuentas (p. ej. 206.01.01 Anticipo de cliente nacional)
están en la posición de Ventas del proyecto, pero no son estimaciones: se
excluyen del "Estimado autorizado" y de lo "Facturado".
"""
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    report_customer_advance = fields.Boolean(
        string='Anticipo de clientes (reportes)',
        help='Reporte Semanal de Dirección: los apuntes de esta cuenta no cuentan '
             'para el estimado autorizado ni para lo facturado del proyecto.',
    )
