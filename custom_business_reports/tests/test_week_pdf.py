# -*- coding: utf-8 -*-
"""Pruebas de la Etapa 7 (PDF Reporte Semanal de Dirección)."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_week_report import WeekReportCase

REPORT = 'custom_business_reports.action_report_week_direction'


@tagged('post_install', '-at_install')
class TestWeekPdf(WeekReportCase):

    def setUp(self):
        super().setUp()
        self.week = self.env['business.report.week'].create({'date': date(2031, 3, 31)})
        self.line = self.env['business.report.week.project'].create({
            'week_id': self.week.id, 'analytic_account_id': self.analytic.id})
        self.week.action_start_capture()
        self.line.neodata_sale = 9000
        self._materiales(self.line).planned_amount = 2000

    def test_report_values(self):
        values = self.env['report.custom_business_reports.report_week_direction']._get_report_values(
            self.week.ids, {})
        report = values['reports'][0]
        self.assertTrue(report['preview'], 'Semana en captura = vista previa')
        self.assertAlmostEqual(report['kpis']['planned'], 2000)
        self.assertAlmostEqual(report['kpis']['real'], 1500)
        self.assertEqual(len(report['projects']), 1)
        self.assertIn('<svg', str(report['partida_chart']))

    def test_render_html(self):
        html, _fmt = self.env['ir.actions.report']._render_qweb_html(REPORT, self.week.ids)
        html = html.decode()
        self.assertIn('Reporte Semanal Dirección', html)
        self.assertIn('CCR Patio', html)
        self.assertIn('VISTA PREVIA', html)
        self.assertIn('Balance de costos por partida', html)

    def test_wizard_and_send(self):
        Wizard = self.env['business.report.week.print'].with_context(active_id=self.week.id,
                                                                      active_model='business.report.week')
        wizard = Wizard.create({})
        self.assertEqual(wizard.project_line_ids, self.line)
        action = wizard.action_print()                        # en captura: vista previa
        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertFalse(self.week.report_attachment_id)
        with self.assertRaises(UserError):
            self.week.action_send_direction_report()
        self.week.action_close()
        action = Wizard.create({}).action_print()             # cerrada: se guarda en la semana
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertTrue(self.week.report_attachment_id)
        self.assertEqual(self.week.report_attachment_id.res_id, self.week.id)
        action = self.week.action_send_direction_report()
        self.assertEqual(action['res_model'], 'mail.compose.message')
