from odoo import api, fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    total_planned_amount = fields.Monetary(
        string="Total previsto", compute="_compute_total_planned_amount"
    )
    total_practical_amount = fields.Monetary(
        string="Total real", compute="_compute_total_practical_amount"
    )

    def _custom_convert_budget_amount(self, line, amount, currency, company, rates):
        if not amount or line.currency_id == currency:
            return amount
        rate_key = (line.currency_id, currency, company, line.date_from)
        if rate_key not in rates:
            rates[rate_key] = line.currency_id._get_conversion_rate(*rate_key)
        return amount * rates[rate_key]

    @api.depends("budget_line.planned_amount")
    def _compute_total_planned_amount(self):
        rates = {}
        for account in self:
            company = account.company_id or self.env.company
            currency = account.currency_id or company.currency_id
            total = sum(
                self._custom_convert_budget_amount(line, line.planned_amount, currency, company, rates)
                for line in account.budget_line
            )
            account.total_planned_amount = currency.round(total)

    def _compute_total_practical_amount(self):
        rates = {}
        for account in self:
            company = account.company_id or self.env.company
            currency = account.currency_id or company.currency_id
            total = sum(
                self._custom_convert_budget_amount(line, line.practical_amount, currency, company, rates)
                for line in account.budget_line
            )
            account.total_practical_amount = currency.round(total)
