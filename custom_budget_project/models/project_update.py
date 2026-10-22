from odoo import api, models


class ProjectUpdate(models.Model):
    _inherit = "project.update"

    @api.model
    def _get_template_values(self, project):
        vals = super()._get_template_values(project)
        if project.account_id and self.env.user.has_group("account.group_account_readonly"):
            items = project._get_position_budget_items(with_action=False) or {}
            if items.get("data"):
                allocated = items["total"]["allocated"]
                spent = items["total"]["spent"]
                vals["position_budget"] = {
                    "data": items["data"],
                    "total": items["total"],
                    "percentage": round(spent / allocated * 100) if allocated else 0,
                    "remaining_percentage": round((allocated - spent) / allocated * 100) if allocated else 0,
                }
                vals["show_activities"] = True
                vals["show_profitability"] = True
        return vals
