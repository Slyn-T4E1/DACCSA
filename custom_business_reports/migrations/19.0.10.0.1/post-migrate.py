# -*- coding: utf-8 -*-
"""Migración 19.0.10.0.1: origen de leads como la lámina 10 (Sin Recompra con
Inadecuado, sin "Ganados en 0's" ni leads sin origen o de Recompra) y color del
acumulado que se ve en modo oscuro."""
from odoo import SUPERUSER_ID, api

from odoo.addons.custom_business_reports.dashboard_defaults import _fix_commercial_v10_1


def migrate(cr, version):
    if not version:
        return
    _fix_commercial_v10_1(api.Environment(cr, SUPERUSER_ID, {}))
