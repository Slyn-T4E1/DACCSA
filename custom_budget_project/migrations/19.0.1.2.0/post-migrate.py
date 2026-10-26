from odoo import SUPERUSER_ID, api

from odoo.addons.custom_budget_project import restore_budget_post_accounts, restore_legacy_budgets


def migrate(cr, version):
    """Recrea los presupuestos de DACSA en Odoo 17 en bases donde el módulo ya estaba
    instalado (el post_init_hook solo corre al instalar). Primero asegura las cuentas de
    las posiciones presupuestarias para que el importe real se calcule igual que en v17."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    restore_budget_post_accounts(env)
    restore_legacy_budgets(env)
