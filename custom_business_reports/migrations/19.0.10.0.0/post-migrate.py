# -*- coding: utf-8 -*-
"""Migración 19.0.10.0.0: "Seguimiento comercial" como el Reporte Comercial
(resumen ejecutivo con desglose SR/R, indicadores del histórico, embudo
Totales / SR / R, venta por trimestre vs meta acumulada, ingenierías y origen
de leads). Acomoda los elementos existentes y agrega los nuevos."""
from odoo import SUPERUSER_ID, api

from odoo.addons.custom_business_reports.dashboard_defaults import _upgrade_commercial_v10


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _upgrade_commercial_v10(env)
