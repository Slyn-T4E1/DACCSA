import json
from datetime import date

from freezegun import freeze_time

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.custom_budget_project import restore_budget_post_accounts


@tagged("post_install", "-at_install")
@freeze_time("2026-10-16")
class TestBudgetProject(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env.user.group_ids += (
            cls.env.ref("account.group_account_manager")
            + cls.env.ref("analytic.group_analytic_accounting")
            + cls.env.ref("project.group_project_manager")
        )
        cls.plan = cls.env["account.analytic.plan"].create({"name": "Proyectos AKRON"})
        cls.analytic = cls.env["account.analytic.account"].create({
            "name": "Proyecto presupuesto", "plan_id": cls.plan.id,
        })
        cls.project = cls.env["project.project"].create({
            "name": "Proyecto con presupuesto", "account_id": cls.analytic.id,
        })
        cls.expense = cls.env["account.account"].create({
            "name": "Alimentos RP", "code": "501.99.26", "account_type": "expense",
        })
        cls.other_expense = cls.env["account.account"].create({
            "name": "Papelería", "code": "501.99.27", "account_type": "expense",
        })
        cls.post = cls.env["account.budget.post"].create({
            "name": "Atención a Cliente", "account_ids": [Command.set(cls.expense.ids)],
        })
        cls.post_2 = cls.env["account.budget.post"].create({
            "name": "Papelería", "account_ids": [Command.set(cls.other_expense.ids)],
        })
        column = cls.plan._column_name()
        Line = cls.env["account.analytic.line"]
        for name, amount, account, line_date in [
            ("Comida cliente", -300.0, cls.expense, "2026-10-05"),
            ("Regalo cliente", -200.0, cls.expense, "2026-11-10"),
            ("Hojas", -50.0, cls.other_expense, "2026-10-07"),
            ("Fuera de periodo", -999.0, cls.expense, "2025-12-31"),
        ]:
            Line.create({
                "name": name, "amount": amount, "general_account_id": account.id,
                "date": line_date, column: cls.analytic.id, "company_id": cls.company.id,
            })

    def _create_budget(self, name="Presupuesto 2026", lines=None, confirm=True):
        budget = self.env["budget.budget"].create({
            "name": name,
            "date_from": "2026-10-01",
            "date_to": "2026-12-31",
            "budget_line": [Command.create(vals) for vals in (lines or [{
                "general_budget_id": self.post.id,
                "analytic_account_id": self.analytic.id,
                "date_from": "2026-10-01",
                "date_to": "2026-12-31",
                "planned_amount": -1000.0,
            }])],
        })
        if confirm:
            budget.action_budget_confirm()
        return budget

    # ----------------------------------------------------------- partidas

    def test_practical_uses_plan_column_and_position_accounts(self):
        line = self._create_budget().budget_line
        self.assertAlmostEqual(line.practical_amount, -500.0)

    def test_practical_without_position_accounts_takes_all_analytic(self):
        line = self._create_budget(lines=[{
            "analytic_account_id": self.analytic.id,
            "date_from": "2026-10-01", "date_to": "2026-12-31", "planned_amount": -1000.0,
        }]).budget_line
        self.assertFalse(line.general_budget_id)
        self.assertAlmostEqual(line.practical_amount, -550.0)

    def test_practical_without_analytic_uses_journal_items(self):
        journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create({"name": "Varios", "code": "VAR", "type": "general"})
        counterpart = self.env["account.account"].search(
            [("account_type", "=", "liability_payable")], limit=1
        ) or self.env["account.account"].create({
            "name": "Proveedores", "code": "201.99.01", "account_type": "liability_payable",
            "reconcile": True,
        })
        move = self.env["account.move"].create({
            "move_type": "entry", "date": "2026-10-10", "journal_id": journal.id,
            "line_ids": [
                Command.create({"account_id": self.expense.id, "debit": 120.0}),
                Command.create({"account_id": counterpart.id, "credit": 120.0}),
            ],
        })
        move.action_post()
        line = self._create_budget(lines=[{
            "general_budget_id": self.post.id,
            "date_from": "2026-10-01", "date_to": "2026-12-31", "planned_amount": -1000.0,
        }]).budget_line
        self.assertAlmostEqual(line.practical_amount, -120.0)

    def test_theoretical_percentage_and_paid_date(self):
        line = self._create_budget().budget_line
        # 16 de 92 días transcurridos.
        self.assertAlmostEqual(line.theoretical_amount, -1000.0 * 16 / 92, places=2)
        self.assertAlmostEqual(line.percentage, -500.0 / (-1000.0 * 16 / 92), places=4)
        self.assertTrue(line.is_above_budget)
        line.paid_date = "2026-12-01"
        self.assertEqual(line.theoretical_amount, 0.0)
        line.paid_date = "2026-10-01"
        self.assertEqual(line.theoretical_amount, -1000.0)

    def test_line_requires_position_or_analytic(self):
        with self.assertRaises(ValidationError):
            self._create_budget(lines=[{
                "date_from": "2026-10-01", "date_to": "2026-12-31", "planned_amount": 10.0,
            }])

    def test_line_dates_inside_budget(self):
        with self.assertRaises(ValidationError):
            self._create_budget(lines=[{
                "analytic_account_id": self.analytic.id,
                "date_from": "2026-10-01", "date_to": "2027-01-31", "planned_amount": 10.0,
            }])

    def test_open_entries(self):
        line = self._create_budget().budget_line
        action = line.action_open_budget_entries()
        entries = self.env["account.analytic.line"].search(action["domain"])
        self.assertEqual(sorted(entries.mapped("amount")), [-300.0, -200.0])

    def test_analytic_account_totals(self):
        self._create_budget()
        self.assertEqual(self.analytic.total_planned_amount, -1000.0)
        self.assertEqual(self.analytic.total_practical_amount, -500.0)

    # ----------------------------------------------------------- tablero

    def test_dashboard_groups_by_budgetary_position(self):
        budget_1 = self._create_budget("Presupuesto A")
        budget_2 = self._create_budget("Presupuesto B", lines=[
            {
                "general_budget_id": self.post.id, "analytic_account_id": self.analytic.id,
                "date_from": "2026-10-01", "date_to": "2026-12-31", "planned_amount": -400.0,
            },
            {
                "general_budget_id": self.post_2.id, "analytic_account_id": self.analytic.id,
                "date_from": "2026-10-01", "date_to": "2026-12-31", "planned_amount": -100.0,
            },
        ])
        self._create_budget("Borrador", confirm=False)

        items = self.project.with_context(allowed_company_ids=self.company.ids)._get_budget_items()
        by_name = {item["name"]: item for item in items["data"]}
        self.assertEqual(set(by_name), {"Atención a Cliente", "Papelería"})

        attention = by_name["Atención a Cliente"]
        self.assertEqual(attention["allocated"], -1400.0)
        self.assertEqual(attention["spent"], -1000.0)  # -500 de cada presupuesto confirmado
        self.assertEqual({b["name"] for b in attention["budgets"]}, {"Presupuesto A", "Presupuesto B"})
        self.assertEqual(attention["action"]["name"], "action_view_budget_lines")
        line_ids = json.loads(attention["action"]["args"])[0][0][2]
        self.assertEqual(
            set(line_ids),
            set((budget_1.budget_line | budget_2.budget_line.filtered(
                lambda line: line.general_budget_id == self.post)).ids),
        )

        stationery = by_name["Papelería"]
        self.assertEqual(stationery["allocated"], -100.0)
        self.assertEqual(stationery["spent"], -50.0)
        self.assertEqual(stationery["budgets"], [], "Con un solo presupuesto no se desglosa (v17)")

        self.assertEqual(items["total"]["allocated"], -1500.0)
        self.assertEqual(items["total"]["spent"], -1050.0)
        self.assertAlmostEqual(items["total"]["progress"], (-1050.0 + 1500.0) / 1500.0)
        self.assertEqual(items["budget_model"], "budget.budget")
        self.assertTrue(items["can_add_budget"])
        self.assertEqual(
            items["form_view_id"], self.env.ref("custom_budget_project.view_budget_form_project_dialog").id
        )

        panel = self.project.with_context(allowed_company_ids=self.company.ids).get_panel_data()
        self.assertEqual(panel["budget_items"]["total"], items["total"])
        self.assertTrue(panel["show_budget_items"])

        action = self.project.action_view_budget_lines(json.loads(attention["action"]["args"])[0])
        self.assertEqual(action["res_model"], "budget.lines")
        self.assertEqual(set(self.env["budget.lines"].search(action["domain"]).ids), set(line_ids))

    def test_dashboard_draft_budget_is_hidden_and_kanban_totals(self):
        self._create_budget("Borrador", confirm=False)
        items = self.project.with_context(allowed_company_ids=self.company.ids)._get_budget_items()
        self.assertEqual(items["data"], [])
        self.assertEqual(self.project.total_budget_amount, 0.0)

        self._create_budget()
        self.project.invalidate_recordset(["total_budget_amount", "total_budget_progress"])
        self.assertEqual(self.project.total_budget_amount, -1000.0)
        self.assertAlmostEqual(self.project.total_budget_progress, (-500.0 + 1000.0) / 1000.0)

    def test_project_update_summary(self):
        self._create_budget()
        values = self.env["project.update"]._get_template_values(self.project)
        self.assertEqual(values["budget"]["total"]["allocated"], -1000.0)
        self.assertEqual(values["budget"]["data"][0]["name"], "Atención a Cliente")

    def test_add_budget_from_dashboard(self):
        Budget = self.env["budget.budget"].with_context(project_update=True, default_project_id=self.project.id)
        defaults = Budget.env["budget.lines"].default_get(["analytic_account_id"])
        self.assertEqual(defaults["analytic_account_id"], self.analytic.id)
        budget = Budget.create({
            "name": "Desde el tablero", "date_from": "2026-10-01", "date_to": "2026-12-31",
            "budget_line": [Command.create({
                "general_budget_id": self.post.id, "analytic_account_id": self.analytic.id,
                "date_from": "2026-10-01", "date_to": "2026-12-31", "planned_amount": -10.0,
            })],
        })
        self.assertEqual(budget.state, "confirm")

    # ----------------------------------------------------------- datos v16

    def test_restore_budget_post_accounts(self):
        post = self.env["account.budget.post"].create({
            "name": "Posición v16", "account_ids": [Command.set(self.other_expense.ids)],
        })
        rows = [
            (post.id, "Posición v16", self.expense.id, self.expense.code),
            (post.id, "Posición v16", self.other_expense.id, self.other_expense.code),
            (post.id, "Otro nombre", self.expense.id, self.expense.code),
            (post.id, "Posición v16", self.expense.id, "000.00.00"),
        ]
        result = restore_budget_post_accounts(self.env, rows)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["existing"], 1)
        self.assertEqual(len(result["skipped"]), 2)
        self.assertEqual(post.account_ids, self.expense | self.other_expense)
        self.assertEqual(restore_budget_post_accounts(self.env, rows)["inserted"], 0)
