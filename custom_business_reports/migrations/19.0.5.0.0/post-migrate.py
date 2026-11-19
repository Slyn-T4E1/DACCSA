# -*- coding: utf-8 -*-
"""Migración a la Etapa 5 (19.0.5.0.0): alerta de margen bajo de 15 % en las
semanas existentes y semana vigente de cada compañía (la última cerrada o, si
no hay, la última) para el tablero."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Alerta de margen bajo: 15 % en las semanas que ya existían
    cr.execute("UPDATE business_report_week SET margin_alert_pct = 0.15 "
               "WHERE margin_alert_pct IS NULL OR margin_alert_pct = 0")
    env['business.report.week'].invalidate_model(['margin_alert_pct'])
    env['business.report.week']._update_current_weeks()
