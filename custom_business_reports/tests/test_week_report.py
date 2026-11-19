# -*- coding: utf-8 -*-
"""Pruebas de la Etapa 3 (Reporte Semanal de Dirección · base)."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.custom_business_reports.hooks import _setup_partidas


class WeekReportCase(TransactionCase):
    """Datos comunes: posición de Materiales, proyecto y apuntes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Cuenta contable de costo y posición presupuestaria "Materiales"
        cls.cost_account = env['account.account'].create({
            'name': 'CCR Materiales', 'code': 'CCR501', 'account_type': 'expense',
        })
        cls.other_account = env['account.account'].create({
            'name': 'CCR Otra', 'code': 'CCR502', 'account_type': 'expense',
        })
        cls.post = env['account.budget.post'].create({
            'name': 'Materiales CCR', 'account_ids': [(6, 0, cls.cost_account.ids)],
            'report_partida': 'materiales',
        })
        # Proyecto = cuenta analítica
        plan = env['account.analytic.plan'].create({'name': 'CCR Proyectos'})
        cls.analytic = env['account.analytic.account'].create({'name': 'CCR Patio', 'plan_id': plan.id})
        cls.column = plan._column_name()
        # Presupuesto confirmado con una línea de Materiales para el proyecto
        budget = env['budget.budget'].create({
            'name': 'CCR Presupuesto', 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31),
            'budget_line': [(0, 0, {
                'general_budget_id': cls.post.id, 'analytic_account_id': cls.analytic.id,
                'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31), 'planned_amount': -5000,
            })],
        })
        budget.action_budget_confirm()
        # Apuntes analíticos: dos de materiales y uno de otra cuenta (no cuenta)
        Line = env['account.analytic.line']
        for amount, day, account in ((-1000, date(2026, 3, 1), cls.cost_account),
                                     (-500, date(2026, 6, 1), cls.cost_account),
                                     (-300, date(2026, 3, 1), cls.other_account)):
            Line.create({'name': 'CCR', 'amount': amount, 'date': day,
                         'general_account_id': account.id, cls.column: cls.analytic.id})

    def _new_week(self, day):
        return self.env['business.report.week'].create({'date': day})

    def _materiales(self, project_line):
        return project_line.partida_line_ids.filtered(lambda p: p.partida == 'materiales')


@tagged('post_install', '-at_install')
class TestWeekReport(WeekReportCase):

    def test_real_with_cutoff(self):
        """El real solo toma apuntes hasta la fecha de corte y de las cuentas de la posición."""
        week = self._new_week(date(2026, 4, 30))
        line = self.env['business.report.week.project'].create({
            'week_id': week.id, 'analytic_account_id': self.analytic.id,
        })
        self.assertEqual(len(line.partida_line_ids), 5, 'Debe crear las 5 partidas de costo')
        week.action_start_capture()
        self.assertAlmostEqual(self._materiales(line).real_amount, 1000)
        self.assertAlmostEqual(line.real_total, 1000)

    def test_week_flow_and_carry_over(self):
        """Captura, cierre, protección de la semana cerrada y arrastre a la siguiente."""
        week1 = self._new_week(date(2026, 4, 30))
        line1 = self.env['business.report.week.project'].create({
            'week_id': week1.id, 'analytic_account_id': self.analytic.id,
        })
        week1.action_start_capture()
        line1.neodata_sale = 10000
        self._materiales(line1).planned_amount = 2000
        self.assertEqual(line1.capture_state, 'complete')
        self.assertAlmostEqual(line1.deviation, 1000)          # 2000 planeado − 1000 real
        self.assertAlmostEqual(line1.neodata_margin, 9000)     # 10000 venta − 1000 real
        week1.action_close()
        self.assertEqual(week1.state, 'closed')
        with self.assertRaises(UserError):
            line1.neodata_sale = 1
        with self.assertRaises(UserError):
            self._materiales(line1).planned_amount = 1

        week2 = self._new_week(date(2026, 7, 1))
        self.assertEqual(week2.previous_week_id, week1)
        week2.action_start_capture()
        line2 = week2.project_line_ids
        self.assertEqual(len(line2), 1, 'Copia el proyecto de la semana anterior')
        self.assertAlmostEqual(line2.neodata_sale_prev, 10000)
        mat2 = self._materiales(line2)
        self.assertAlmostEqual(mat2.planned_prev, 2000)
        self.assertAlmostEqual(mat2.planned_amount, 2000)
        self.assertAlmostEqual(mat2.real_prev, 1000)
        self.assertAlmostEqual(mat2.real_amount, 1500)
        self.assertAlmostEqual(line2.week_cost, 500)           # 1500 − 1000
        line2.neodata_sale = 10800
        self.assertAlmostEqual(line2.neodata_advance, 800)
        self.assertAlmostEqual(line2.week_difference, 300)     # 800 avance − 500 costo
        # La semana cerrada conserva su foto aunque cambie el real
        self.assertAlmostEqual(self._materiales(line1).real_amount, 1000)

    def test_close_requires_capture(self):
        """No se puede cerrar con proyectos pendientes de captura."""
        week = self._new_week(date(2026, 4, 30))
        self.env['business.report.week.project'].create({
            'week_id': week.id, 'analytic_account_id': self.analytic.id,
        })
        week.action_start_capture()
        with self.assertRaises(UserError):
            week.action_close()

    def test_partida_setup_by_name(self):
        """El hook reconoce el tipo de partida por el nombre de la posición."""
        Post = self.env['account.budget.post']
        posts = {name: Post.create({'name': name, 'account_ids': [(6, 0, self.cost_account.ids)]})
                 for name in ('Materiales PM', 'Mano de Obra PM', 'Equipo y Herramientas PM',
                              'Subcontratistas PM', 'Indirectos PM', 'Ventas PM',
                              'Anticipo a Proveedores PM', 'Inventario PM',
                              'Ingresos AVCG', 'MO PA', 'MAT ISO', 'Herr')}
        _setup_partidas(self.env)
        expected = {'Materiales PM': 'materiales', 'Mano de Obra PM': 'mano_obra',
                    'Equipo y Herramientas PM': 'equipo_herramienta', 'Subcontratistas PM': 'subcontratistas',
                    'Indirectos PM': 'indirectos', 'Ventas PM': 'ventas',
                    'Anticipo a Proveedores PM': 'otro', 'Inventario PM': 'otro',
                    'Ingresos AVCG': 'ventas', 'MO PA': 'mano_obra', 'MAT ISO': 'materiales',
                    'Herr': 'equipo_herramienta'}
        for name, partida in expected.items():
            self.assertEqual(posts[name].report_partida, partida, name)


@tagged('post_install', '-at_install')
class TestWeekReportFinance(TransactionCase):
    """Etapa 4: valor contrato, estimado autorizado, facturado y márgenes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Account = env['account.account']
        cls.cost_account = Account.create({'name': 'CCR Materiales', 'code': 'CCR601', 'account_type': 'expense'})
        cls.income_account = Account.create({'name': 'CCR Ingresos por obras', 'code': 'CCR401', 'account_type': 'income'})
        cls.advance_account = Account.create({
            'name': 'CCR Anticipo de cliente', 'code': 'CCR206', 'account_type': 'liability_current',
            'report_customer_advance': True,
        })
        Post = env['account.budget.post']
        cost_post = Post.create({'name': 'Materiales F', 'account_ids': [(6, 0, cls.cost_account.ids)],
                                 'report_partida': 'materiales'})
        sales_post = Post.create({'name': 'Ventas F', 'report_partida': 'ventas',
                                  'account_ids': [(6, 0, (cls.income_account | cls.advance_account).ids)]})
        plan = env['account.analytic.plan'].create({'name': 'CCR Proyectos F'})
        cls.analytic = env['account.analytic.account'].create({'name': 'CCR Nave', 'plan_id': plan.id})
        column = plan._column_name()
        budget = env['budget.budget'].create({
            'name': 'CCR Presupuesto F', 'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31),
            'budget_line': [(0, 0, {'general_budget_id': post.id, 'analytic_account_id': cls.analytic.id,
                                    'date_from': date(2026, 1, 1), 'date_to': date(2026, 12, 31),
                                    'planned_amount': amount})
                            for post, amount in ((cost_post, -6000), (sales_post, 10000))],
        })
        budget.action_budget_confirm()
        Line = env['account.analytic.line']
        for amount, account, day in ((-4000, cls.cost_account, date(2026, 3, 1)),
                                     (7000, cls.income_account, date(2026, 3, 1)),   # estimación
                                     (500, cls.advance_account, date(2026, 3, 1)),   # anticipo: no cuenta
                                     (2000, cls.income_account, date(2026, 9, 1))):  # después del corte
            Line.create({'name': 'CCR', 'amount': amount, 'date': day,
                         'general_account_id': account.id, column: cls.analytic.id})
        # Pedidos de venta: uno antes del corte (80% a la cuenta) y otro después
        partner = env['res.partner'].create({'name': 'CCR Cliente'})
        product = env['product.product'].create({'name': 'CCR Obra', 'type': 'service', 'list_price': 1})
        cls.orders = env['sale.order']
        for amount, day in ((10000, '2026-02-01 10:00:00'), (3000, '2026-09-01 10:00:00')):
            order = env['sale.order'].create({
                'partner_id': partner.id, 'date_order': day,
                'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1, 'price_unit': amount,
                                       'tax_ids': [(5, 0, 0)],
                                       'analytic_distribution': {str(cls.analytic.id): 80}})],
            })
            order.action_confirm()
            order.date_order = day   # confirmar cambia la fecha del pedido
            cls.orders |= order
        # Factura de cliente publicada antes del corte: 6000 de obra
        invoice = env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': partner.id, 'invoice_date': date(2026, 3, 15),
            'invoice_line_ids': [(0, 0, {'name': 'Estimación 1', 'quantity': 1, 'price_unit': 6000,
                                         'account_id': cls.income_account.id, 'tax_ids': [(5, 0, 0)],
                                         'analytic_distribution': {str(cls.analytic.id): 100}})],
        })
        invoice.action_post()

    def test_finance_amounts(self):
        week = self.env['business.report.week'].create({'date': date(2026, 4, 30)})
        line = self.env['business.report.week.project'].create({
            'week_id': week.id, 'analytic_account_id': self.analytic.id,
        })
        week.action_start_capture()
        self.assertAlmostEqual(line.contract_amount, 8000)            # 80% de 10000; el de sept. no
        # Estimado: ingresos analíticos hasta el corte sin anticipos. La
        # factura también generó apunte analítico de 6000 en la cuenta de ingresos.
        self.assertAlmostEqual(line.estimate_amount, 13000)           # 7000 + 6000
        self.assertAlmostEqual(line.invoiced_amount, 6000)
        self.assertAlmostEqual(line.real_total, 4000)
        self.assertAlmostEqual(line.remaining_estimate, 8000 - 13000)
        self.assertAlmostEqual(line.operating_margin, 9000)           # 13000 − 4000
        self.assertAlmostEqual(line.operating_margin_pct, 9000 / 13000)
        self.assertIn(line, line.history_line_ids)
        # Los accesos abren sin errores
        for method in ('action_open_detail', 'action_open_estimate_entries', 'action_open_invoice_lines',
                       'action_open_sale_orders', 'action_open_budget_lines', 'action_open_partida_analysis',
                       'action_open_history'):
            self.assertTrue(getattr(line, method)(), method)
        self.assertEqual(line.action_open_sale_orders()['domain'], [('id', 'in', self.orders[:1].ids)])

    def test_finance_frozen_and_carry_over(self):
        """Al cerrar, los datos financieros quedan congelados; el % plan se arrastra."""
        Week = self.env['business.report.week']
        week1 = Week.create({'date': date(2026, 4, 30)})
        line1 = self.env['business.report.week.project'].create({
            'week_id': week1.id, 'analytic_account_id': self.analytic.id, 'planned_margin_pct': 0.1884,
        })
        week1.action_start_capture()
        line1.neodata_sale = 12000
        line1.partida_line_ids.filtered(lambda p: p.partida == 'materiales').planned_amount = 5000
        week1.action_close()
        week2 = Week.create({'date': date(2026, 9, 30)})
        week2.action_start_capture()
        line2 = week2.project_line_ids
        self.assertAlmostEqual(line2.planned_margin_pct, 0.1884)
        self.assertAlmostEqual(line2.contract_amount, 8000 + 2400)
        self.assertAlmostEqual(line2.estimate_amount, 15000)
        self.assertAlmostEqual(line1.estimate_amount, 13000, msg='La semana cerrada no cambia')
        self.assertEqual(line2.history_line_ids, line2 | line1)


@tagged('post_install', '-at_install')
class TestWeekDashboard(WeekReportCase):
    """Etapa 5: semana vigente, resumen por partida, alertas y tablero."""

    def setUp(self):
        super().setUp()
        # Semanas que ya existan en la base no deben estorbar: se pasan a otra compañía
        Week = self.env['business.report.week']
        other = self.env['res.company'].create({'name': 'CCR otra compañía'})
        Week.search([]).write({'company_id': other.id})

    def _week_with_line(self, day, sale, planned):
        week = self._new_week(day)
        week.action_start_capture()
        line = week.project_line_ids or self.env['business.report.week.project'].create({
            'week_id': week.id, 'analytic_account_id': self.analytic.id})
        week.action_refresh_real()
        line.neodata_sale = sale
        self._materiales(line).planned_amount = planned
        return week, line

    def test_current_week(self):
        Week = self.env['business.report.week']
        week1, _line1 = self._week_with_line(date(2030, 4, 30), 10000, 2000)
        self.assertTrue(week1.is_current, 'Sin semanas cerradas, la última es la vigente')
        week1.action_close()
        week2, line2 = self._week_with_line(date(2030, 7, 1), 10800, 2100)
        self.assertTrue(week1.is_current, 'La vigente es la última cerrada')
        self.assertFalse(week2.is_current)
        self.assertFalse(line2.week_is_current)
        week2.action_close()
        self.assertTrue(week2.is_current)
        self.assertTrue(line2.week_is_current)
        self.assertTrue(all(line2.partida_line_ids.mapped('week_is_current')))
        self.assertFalse(week1.is_current)
        self.assertEqual(Week.search_count([('is_current', '=', True),
                                            ('company_id', '=', self.env.company.id)]), 1)

    def test_summary_and_alert(self):
        week, line = self._week_with_line(date(2030, 4, 30), 10000, 2000)
        self.env.flush_all()
        self.env.invalidate_all()
        summary = week.partida_summary_ids.filtered(lambda s: s.partida == 'materiales')
        # Corte 2030: entran los dos apuntes de materiales (1000 + 500)
        self.assertAlmostEqual(summary.planned_amount, 2000)
        self.assertAlmostEqual(summary.real_amount, 1500)
        self.assertAlmostEqual(summary.deviation, 500)
        self.assertAlmostEqual(summary.deviation_pct, 0.25)
        self.assertAlmostEqual(week.deviation_pct_total, 0.25)
        # Gráficas: planeado y real en renglones separados; tendencia por semana
        cost = self.env['business.report.dashboard.cost'].search([('week_id', '=', week.id),
                                                                   ('partida', '=', 'materiales')])
        self.assertEqual(sorted(cost.mapped('amount')), [1500, 2000])
        trend = self.env['business.report.dashboard.trend'].search([('week_id', '=', week.id)])
        self.assertEqual(dict((t.serie, t.amount) for t in trend), {'1_balance': 500, '2_sale': 10000})  # sin semana anterior, el avance es toda la venta
        # Sin estimado autorizado no hay alerta de margen
        self.assertFalse(line.margin_alert)
        for method in ('action_open_cost_chart', 'action_open_trend_chart', 'action_open_dashboard'):
            self.assertTrue(getattr(week, method)(), method)
