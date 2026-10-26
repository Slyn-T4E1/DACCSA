from odoo import SUPERUSER_ID, api

from odoo.addons.custom_budget_project import restore_budget_post_accounts


def migrate(cr, version):
    """Restaura la relación posición presupuestaria → cuentas contables de DACSA (v17)
    en bases donde el módulo ya estaba instalado (el post_init_hook solo corre al instalar)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    restore_budget_post_accounts(env)
