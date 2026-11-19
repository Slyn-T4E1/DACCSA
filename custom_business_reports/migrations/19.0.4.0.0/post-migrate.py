# -*- coding: utf-8 -*-
"""Migración a la Etapa 4 (19.0.4.0.0): marca la cuenta 206.01.01 Anticipo de
cliente nacional como anticipo (no cuenta en estimado autorizado ni facturado)
y calcula los datos financieros de las semanas que no están cerradas."""
from odoo import SUPERUSER_ID, api

from odoo.addons.custom_business_reports.hooks import _setup_advance_accounts


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _setup_advance_accounts(env)
    for week in env['business.report.week'].search([('state', '!=', 'closed')]):
        week.project_line_ids._refresh_real_amounts(week.date)
