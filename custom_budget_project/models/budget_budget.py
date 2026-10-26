from odoo import api, models


class Budget(models.Model):
    _inherit = "budget.budget"

    @api.model_create_multi
    def create(self, vals_list):
        budgets = super().create(vals_list)
        # v17: un presupuesto creado desde el botón "Agregar presupuesto" del
        # tablero del proyecto queda confirmado para verse de inmediato.
        if len(budgets) == 1 and self.env.context.get("position_budget_from_project"):
            budgets.action_budget_confirm()
        return budgets
