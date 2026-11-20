# -*- coding: utf-8 -*-
"""Migración 19.0.11.0.0: los menús del módulo se mueven a la app "Tableros
DACSA" (los ids no cambian, la actualización los mueve). El menú
Configuración deja de pedir el grupo de administrador de tableros, porque ahora
también trae opciones para gerentes de ventas y de proyecto; cada opción
conserva su propio grupo. (El XML no puede quitar grupos de un menú existente.)"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env.ref('custom_business_reports.menu_business_dashboard_config_root', raise_if_not_found=False)
    if menu:
        menu.group_ids = [(5, 0, 0)]
