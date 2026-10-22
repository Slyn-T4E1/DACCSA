from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class BudgetLines(models.Model):
    """Lleva budget.lines (base_account_budget) al comportamiento de
    crossovered.budget.lines de Odoo 17."""

    _inherit = "budget.lines"

    # v17: la posición presupuestaria es opcional (basta con posición o cuenta analítica).
    general_budget_id = fields.Many2one(required=False)
    analytic_plan_id = fields.Many2one(
        "account.analytic.plan", string="Plan analítico",
        related="analytic_account_id.plan_id", readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True
    )
    budget_state = fields.Selection(
        related="budget_id.state", string="Estado del presupuesto", store=True, readonly=True
    )
    is_above_budget = fields.Boolean(compute="_compute_is_above_budget")

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        # v17: al agregar un presupuesto desde el tablero, la línea toma la
        # cuenta analítica del proyecto.
        if self.env.context.get("project_update") and "analytic_account_id" in fields_list:
            project_id = self.env.context.get("default_project_id") or self.env.context.get("active_id")
            project = self.env["project.project"].browse(project_id).exists() if project_id else False
            if project and project.account_id and not defaults.get("analytic_account_id"):
                defaults["analytic_account_id"] = project.account_id.id
        return defaults

    @api.depends("budget_id", "general_budget_id", "analytic_account_id")
    def _compute_display_name(self):
        for line in self:
            parts = [line.budget_id.name, line.general_budget_id.name, line.analytic_account_id.name]
            line.display_name = " - ".join(part for part in parts if part)

    # -------------------------------------------------------------------------
    # Importe real (v17)
    # -------------------------------------------------------------------------

    def _custom_get_accounts_from_line(self):
        """(modelo, campo de cuenta, ids) como _get_accounts_from_line de v17."""
        self.ensure_one()
        if self.analytic_account_id:
            return (
                "account.analytic.line",
                self.analytic_account_id.plan_id._column_name(),
                set(self.analytic_account_id.ids),
            )
        return "account.move.line", "account_id", set(self.general_budget_id.account_ids.ids)

    def _compute_practical_amount(self):
        groups = defaultdict(lambda: defaultdict(set))  # {(model, fname): {(from, to): ids}}
        for line in self:
            if not line.date_from or not line.date_to:
                continue
            model, fname, accounts = line._custom_get_accounts_from_line()
            if accounts:
                groups[(model, fname)][(line.date_from, line.date_to)].update(accounts)

        agg_general = defaultdict(float)  # (model, fname, from, to, account, general) -> amount
        agg_analytic = defaultdict(float)  # (model, fname, from, to, account) -> amount
        for (model, fname), by_date in groups.items():
            is_move_line = model == "account.move.line"
            general_fname = "account_id" if is_move_line else "general_account_id"
            aggregate = "balance:sum" if is_move_line else "amount:sum"
            for (date_from, date_to), account_ids in by_date.items():
                domain = [
                    ("date", ">=", date_from),
                    ("date", "<=", date_to),
                    (fname, "in", list(account_ids)),
                ]
                if is_move_line:
                    domain.append(("parent_state", "=", "posted"))
                groupby = [fname] if fname == general_fname else [fname, general_fname]
                for group in self.env[model]._read_group(domain, groupby, [aggregate]):
                    account = group[0]
                    general_account = group[0] if fname == general_fname else group[1]
                    amount = group[-1]
                    if is_move_line:
                        amount = -amount
                    agg_general[(model, fname, date_from, date_to, account.id, general_account.id)] += amount
                    agg_analytic[(model, fname, date_from, date_to, account.id)] += amount

        for line in self:
            if not line.date_from or not line.date_to:
                line.practical_amount = 0.0
                continue
            model, fname, accounts = line._custom_get_accounts_from_line()
            general_accounts = line.general_budget_id.account_ids
            key = (model, fname, line.date_from, line.date_to)
            if general_accounts:
                line.practical_amount = sum(
                    agg_general.get((*key, account, general_account), 0.0)
                    for account in accounts
                    for general_account in general_accounts.ids
                )
            else:
                line.practical_amount = sum(agg_analytic.get((*key, account), 0.0) for account in accounts)

    # -------------------------------------------------------------------------
    # Importe teórico, logro y sobregiro (v17)
    # -------------------------------------------------------------------------

    @api.depends("date_from", "date_to", "paid_date", "planned_amount")
    def _compute_theoretical_amount(self):
        today = fields.Date.today()
        for line in self:
            if line.paid_date:
                theo_amt = 0.0 if today <= line.paid_date else line.planned_amount
            elif not line.date_from or not line.date_to:
                theo_amt = 0.0
            else:
                # Se incluyen el día inicial y el final (1 al 30 de abril = 30 días).
                line_timedelta = line.date_to - line.date_from + timedelta(days=1)
                elapsed_timedelta = today - line.date_from + timedelta(days=1)
                if elapsed_timedelta.days < 0:
                    theo_amt = 0.0
                elif line_timedelta.days > 0 and today < line.date_to:
                    theo_amt = (
                        elapsed_timedelta.total_seconds() / line_timedelta.total_seconds()
                    ) * line.planned_amount
                else:
                    theo_amt = line.planned_amount
            line.theoretical_amount = theo_amt

    @api.depends("theoretical_amount", "practical_amount")
    def _compute_percentage(self):
        for line in self:
            line.percentage = (
                float((line.practical_amount or 0.0) / line.theoretical_amount)
                if line.theoretical_amount
                else 0.0
            )

    def _compute_is_above_budget(self):
        for line in self:
            if line.theoretical_amount >= 0:
                line.is_above_budget = line.practical_amount > line.theoretical_amount
            else:
                line.is_above_budget = line.practical_amount < line.theoretical_amount

    # -------------------------------------------------------------------------
    # Validaciones y ayudas de captura (v17)
    # -------------------------------------------------------------------------

    @api.constrains("general_budget_id", "analytic_account_id", "date_from")
    def _check_analytic_or_budgetary_position(self):
        for line in self:
            if not line.analytic_account_id and not line.general_budget_id:
                raise ValidationError(_(
                    "Debe capturar al menos una posición presupuestaria o una cuenta "
                    "analítica en la línea del presupuesto."
                ))

    @api.constrains("date_from", "date_to")
    def _check_line_dates_inside_budget(self):
        for line in self:
            budget_from, budget_to = line.budget_id.date_from, line.budget_id.date_to
            for label, value in ((_("Fecha inicial"), line.date_from), (_("Fecha final"), line.date_to)):
                if value and ((budget_from and value < budget_from) or (budget_to and value > budget_to)):
                    raise ValidationError(_(
                        "La %(field)s de la línea debe estar dentro del periodo del presupuesto.",
                        field=label.lower(),
                    ))

    @api.onchange("date_from", "date_to")
    def _onchange_dates(self):
        domains = []
        if self.date_from:
            domains.append(Domain("date_from", "<=", self.date_from) | Domain("date_from", "=", False))
        if self.date_to:
            domains.append(Domain("date_to", ">=", self.date_to) | Domain("date_to", "=", False))
        if domains and not self.budget_id.filtered_domain(Domain.AND(domains)):
            self.budget_id = self.env["budget.budget"].search(Domain.AND(domains), limit=1)

    @api.onchange("budget_id")
    def _onchange_budget_id(self):
        if self.budget_id:
            self.date_from = self.date_from or self.budget_id.date_from
            self.date_to = self.date_to or self.budget_id.date_to

    # -------------------------------------------------------------------------
    # Acciones (v17)
    # -------------------------------------------------------------------------

    def action_open_budget_entries(self):
        self.ensure_one()
        if self.analytic_account_id:
            action = self.env["ir.actions.act_window"]._for_xml_id("analytic.account_analytic_line_action_entries")
            domain = [
                ("auto_account_id", "=", self.analytic_account_id.id),
                ("date", ">=", self.date_from),
                ("date", "<=", self.date_to),
            ]
            if self.general_budget_id.account_ids:
                domain.append(("general_account_id", "in", self.general_budget_id.account_ids.ids))
        else:
            action = self.env["ir.actions.act_window"]._for_xml_id("account.action_account_moves_all_a")
            domain = [
                ("account_id", "in", self.general_budget_id.account_ids.ids),
                ("date", ">=", self.date_from),
                ("date", "<=", self.date_to),
                ("parent_state", "=", "posted"),
            ]
        action["domain"] = domain
        action["context"] = {"create": False}
        return action
