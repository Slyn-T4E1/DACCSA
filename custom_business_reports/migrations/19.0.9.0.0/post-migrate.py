# -*- coding: utf-8 -*-
"""Migración 19.0.9.0.0: "Listados comerciales" con una sección por lámina del
Reporte Comercial (ganados, perdidos, cancelados, en pausa, pipeline abierto y
prospección), cada una con indicadores Sin Recompra / Recompra, gráfica y
listado. Reemplaza los 5 listados anteriores; lo demás no se toca."""
from odoo import SUPERUSER_ID, api

from odoo.addons.custom_business_reports.dashboard_defaults import _upgrade_commercial_lists


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _upgrade_commercial_lists(env)
