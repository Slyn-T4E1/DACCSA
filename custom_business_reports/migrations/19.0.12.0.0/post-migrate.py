# -*- coding: utf-8 -*-
"""Migración 19.0.12.0.0: gráficas que faltaban en el "Reporte semanal
Dirección" según las sesiones del 28/10 y 13/11 y el documento base
(desviación por cuenta analítica, costos y margen NeoData por proyecto,
balance financiero, histórico semanal, margen semanal y diferencia de costos
por partida). Acomoda los elementos existentes y agrega los nuevos."""
from odoo import SUPERUSER_ID, api

from odoo.addons.custom_business_reports.dashboard_defaults import _upgrade_week_report_v12


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _upgrade_week_report_v12(env)
