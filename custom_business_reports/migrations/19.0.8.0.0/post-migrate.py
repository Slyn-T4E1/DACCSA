# -*- coding: utf-8 -*-
"""Migración 19.0.8.0.0: agrega al tablero "Seguimiento comercial" que ya existe
los elementos nuevos (meta de venta, avance vs meta, tabla "Invitaciones a
cotizar, mes a mes", venta vs meta mensual y antigüedad del pipeline). No
cambia ni duplica los elementos que ya tiene."""
from odoo import SUPERUSER_ID, api

from odoo.addons.custom_business_reports.dashboard_defaults import _ensure_widgets


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _ensure_widgets(env, since='19.0.8.0.0')
