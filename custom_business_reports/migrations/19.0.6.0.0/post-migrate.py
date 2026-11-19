# -*- coding: utf-8 -*-
"""Migración a la Etapa 6 (19.0.6.0.0): crea los tableros de fábrica de la app
"Tableros DACSA". Los tableros de la app Tableros (hoja de cálculo) se borran
solos porque ya no están en los datos del módulo."""
from odoo import SUPERUSER_ID, api

from odoo.addons.custom_business_reports.dashboard_defaults import _setup_dashboards


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _setup_dashboards(env)
