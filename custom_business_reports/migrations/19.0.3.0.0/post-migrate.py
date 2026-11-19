# -*- coding: utf-8 -*-
"""Migración a la Etapa 3 (19.0.3.0.0): tipo de partida de las posiciones
presupuestarias existentes, reconocido por su nombre."""
from odoo import SUPERUSER_ID, api

from odoo.addons.custom_business_reports.hooks import _setup_partidas


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _setup_partidas(env)
