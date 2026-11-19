# -*- coding: utf-8 -*-
"""Migración a la Etapa 2 (19.0.2.0.0) en bases que ya tenían la Etapa 1.

Los campos nuevos guardados (invitación a cotizar, resultado) los calcula
Odoo solo al actualizar. Aquí solo falta marcar las etapas "Enviada" y
"En Pausa" para los listados del pipeline.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.custom_business_reports.hooks import _setup_open_status


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _setup_open_status(env)
