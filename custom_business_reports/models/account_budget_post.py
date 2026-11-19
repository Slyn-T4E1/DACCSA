# -*- coding: utf-8 -*-
"""Tipo de partida en las posiciones presupuestarias (account.budget.post).

Cada proyecto tiene sus propias posiciones (Materiales PM, Materiales NMM...).
El tipo de partida las agrupa para el Reporte Semanal de Dirección: el real
de "Materiales" de un proyecto es la suma de sus posiciones de tipo
Materiales, y el resumen de Dirección suma todos los proyectos.
"""
from odoo import fields, models

from .const import PARTIDA_SELECTION


class AccountBudgetPost(models.Model):
    _inherit = 'account.budget.post'

    report_partida = fields.Selection(
        PARTIDA_SELECTION,
        string='Tipo de partida',
        index=True,
        help='Partida del Reporte Semanal de Dirección a la que suma esta '
             'posición. "Otro" no cuenta como costo (anticipos, inventario).',
    )
