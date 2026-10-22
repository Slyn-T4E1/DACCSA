import json
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.fields import Domain

EXCLUDED_BUDGET_STATES = ("draft", "cancel")


class ProjectProject(models.Model):
    """Presupuestos por posición presupuestaria (base_account_budget) en el tablero del
    proyecto, con el comportamiento de project_account_budget de Odoo 17.

    Se muestran en una sección propia: la sección nativa "Presupuestos" de Odoo 19
    (budget.analytic) se conserva sin cambios.
    """

    _inherit = "project.project"

    position_budget_amount = fields.Monetary(
        string="Total previsto (posiciones presupuestarias)",
        compute="_compute_position_budget",
        export_string_translation=False,
    )
    position_budget_progress = fields.Float(
        string="Avance del presupuesto (posiciones presupuestarias)",
        compute="_compute_position_budget",
        export_string_translation=False,
    )

    def _position_budget_lines_domain(self):
        return [
            ("analytic_account_id", "in", self.account_id.ids),
            ("budget_id", "!=", False),
            ("budget_id.state", "not in", EXCLUDED_BUDGET_STATES),
        ]

    @api.depends("account_id")
    def _compute_position_budget(self):
        """Total previsto y avance para el indicador del kanban (v17)."""
        lines = self.env["budget.lines"].sudo().search(self._position_budget_lines_domain())
        totals = defaultdict(lambda: {"planned": 0.0, "practical": 0.0})
        for line in lines:
            totals[line.analytic_account_id.id]["planned"] += line.planned_amount
            totals[line.analytic_account_id.id]["practical"] += line.practical_amount
        for project in self:
            planned = totals[project.account_id.id]["planned"] if project.account_id else 0.0
            practical = totals[project.account_id.id]["practical"] if project.account_id else 0.0
            project.position_budget_amount = planned
            project.position_budget_progress = planned and (practical - planned) / abs(planned)

    def action_view_position_budget_lines(self, domain=None):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "budget.lines",
            "name": _("Partidas del presupuesto"),
            "domain": Domain.AND([
                [
                    ("analytic_account_id", "=", self.account_id.id),
                    ("budget_id.state", "not in", EXCLUDED_BUDGET_STATES),
                ],
                domain or [],
            ]),
            "context": {"create": False, "edit": False},
            "view_mode": "list",
            "views": [(self.env.ref("custom_budget_project.view_budget_lines_project_list").id, "list")],
        }

    # ----------------------------
    #  Tablero del proyecto
    # ----------------------------

    def get_panel_data(self):
        panel_data = super().get_panel_data()
        panel_data["position_budget_items"] = self._get_position_budget_items()
        panel_data["show_position_budget_items"] = bool(self.account_id)
        return panel_data

    def get_position_budget_items(self):
        self.ensure_one()
        if self.account_id and self.env.user.has_group("project.group_project_user"):
            return self._get_position_budget_items(True)
        return {}

    def _get_position_budget_items(self, with_action=True):
        self.ensure_one()
        if not self.account_id:
            return
        lines = self.env["budget.lines"].sudo().search(
            self._position_budget_lines_domain(),
            order="general_budget_id, budget_id, id",
        )
        allowed_company_ids = self.env.context.get("allowed_company_ids", [])
        has_company_access = any(line.company_id.id in allowed_company_ids for line in lines)
        user = self.env.user
        can_see_budget_items = with_action and has_company_access and (
            user.has_group("account.group_account_readonly")
            or user.has_group("analytic.group_analytic_accounting")
        )

        per_position = {}
        total_allocated = total_spent = 0.0
        for line in lines:
            position = line.general_budget_id
            item = per_position.setdefault(position.id or 0, {
                "id": position.id or 0,
                "name": position.display_name or False,
                "allocated": 0.0,
                "spent": 0.0,
                "_budgets": {},
                "_ids": [],
            })
            allocated, spent = line.planned_amount, line.practical_amount
            item["allocated"] += allocated
            item["spent"] += spent
            item["_ids"].append(line.id)
            budget = item["_budgets"].setdefault(line.budget_id.id, {
                "id": line.budget_id.id,
                "name": line.budget_id.display_name,
                "allocated": 0.0,
                "spent": 0.0,
            })
            budget["allocated"] += allocated
            budget["spent"] += spent
            total_allocated += allocated
            total_spent += spent

        data = []
        for item in per_position.values():
            budgets = list(item.pop("_budgets").values())
            ids = item.pop("_ids")
            item["progress"] = item["allocated"] and (item["spent"] - item["allocated"]) / abs(item["allocated"])
            if can_see_budget_items:
                for budget in budgets:
                    budget["progress"] = budget["allocated"] and (
                        (budget["spent"] - budget["allocated"]) / abs(budget["allocated"])
                    )
                # v17: el detalle por presupuesto solo se muestra si hay más de uno.
                item["budgets"] = budgets if len(budgets) > 1 else []
                item["action"] = {
                    "name": "action_view_position_budget_lines",
                    "type": "object",
                    "args": json.dumps([[("id", "in", ids)]]),
                }
            else:
                item["budgets"] = []
            data.append(item)

        can_add_budget = with_action and user.has_group("account.group_account_user")
        budget_items = {
            "data": data,
            "total": {
                "allocated": total_allocated,
                "spent": total_spent,
                "progress": total_allocated and (total_spent - total_allocated) / abs(total_allocated),
            },
            "can_add_budget": can_add_budget,
        }
        if can_add_budget:
            budget_items["form_view_id"] = self.env.ref("custom_budget_project.view_budget_form_project_dialog").id
            budget_items["company_id"] = self.company_id.id or self.env.company.id
        return budget_items
