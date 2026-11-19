# -*- coding: utf-8 -*-
"""Pruebas de la Etapa 3 (Reporte Semanal de Dirección · base)."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.custom_business_reports.hooks import _setup_partidas


@tagged('post_install', '-at_install')
class TestWeekReport(TransactionCase):

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
