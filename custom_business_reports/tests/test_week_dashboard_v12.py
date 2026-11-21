# -*- coding: utf-8 -*-
"""Pruebas de 19.0.12.0.0: gráficas del Reporte semanal Dirección."""
from datetime import date

from odoo.tests import tagged

from odoo.addons.custom_business_reports.dashboard_defaults import (
    OLD_WEEK_NAMES, WEEK_REPORT, _upgrade_week_report_v12,
)
from odoo.addons.custom_business_reports.tests.test_week_report import WeekReportCase


@tagged('post_install', '-at_install')
class TestWeekDashboardV12(WeekReportCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Week = cls.env['business.report.week']
        cls.week1 = Week.create({'date': date(2026, 4, 30)})
        line1 = cls.env['business.report.week.project'].create({
            'week_id': cls.week1.id, 'analytic_account_id': cls.analytic.id})
        cls.week1.action_start_capture()
        line1.neodata_sale = 3000
        line1.partida_line_ids.filtered(lambda p: p.partida == 'materiales').planned_amount = 2000
        cls.week1.action_close()
        cls.week2 = Week.create({'date': date(2026, 6, 30)})
        cls.week2.action_start_capture()
        cls.line2 = cls.week2.project_line_ids
        cls.line2.neodata_sale = 5000
        cls.line2.partida_line_ids.filtered(lambda p: p.partida == 'materiales').planned_amount = 1200
        cls.week2.action_close()
        cls.dashboard = cls.env.ref('custom_business_reports.dashboard_week_report')
        cls.semana = cls.dashboard.filter_ids.filtered(lambda f: f.field_name == 'week_id')
        cls.proyecto = cls.dashboard.filter_ids.filtered(lambda f: f.field_name == 'analytic_account_id')

    def _values(self, week=None):
        # Solo el proyecto de la prueba (la base puede traer otras semanas de ejemplo)
        return {str(self.semana.id): [(week or self.week2).id], str(self.proyecto.id): [self.analytic.id]}

    def _widgets(self, week=None):
        data = self.dashboard.get_dashboard_data(self._values(week))
        self.assertFalse([(w['title'], w['error']) for w in data['widgets'] if w['error']])
        return {w['title']: w for w in data['widgets']}

    def test_new_charts(self):
        widgets = self._widgets()
        for item in WEEK_REPORT['widgets']:
            if not item.get('hidden'):
                self.assertIn(item['name'], widgets)
        self.assertNotIn(OLD_WEEK_NAMES[0], widgets)
        # Desviación por cuenta analítica: 1200 − 1500 = −300, barra en rojo (color por signo)
        chart = widgets['Desviación por cuenta analítica']
        self.assertEqual(chart['datasets'][0]['data'], [-300.0])
        self.assertEqual(chart['datasets'][0]['color_mode'], 'sign')
        # Histórico: una barra por semana aunque se elija una sola semana
        history = widgets['Margen operativo NeoData por semana']
        self.assertEqual(history['datasets'][0]['data'], [3000 - 1000, 5000 - 1500])
        # Margen semanal: avance 5000 − 3000, costo de la semana 1500 − 1000
        table = widgets['Margen semanal por proyecto']
        values = [c['value'] for c in table['rows'][0]['cells']]
        self.assertEqual(values, [5000, 3000, 2000, 500, 1500])
        # Diferencia de costos por partida: Δ planeado −800, Δ real 500 → −1300
        delta = widgets['Diferencia de costos semanal por partida']
        index = delta['keys'].index('materiales')
        self.assertEqual([d['data'][index] for d in delta['datasets']], [-800, 500, -1300])
        # Balance financiero: una serie por concepto
        self.assertEqual(len(widgets['Balance financiero por proyecto']['datasets']), 7)

    def test_compare_other_week(self):
        """Otra semana: las gráficas de la semana llevan comparativo; las históricas no."""
        data = self.dashboard.get_dashboard_data(
            self._values(),
            {'mode': 'record', 'filter_id': self.semana.id, 'record_id': self.week1.id})
        widgets = {w['title']: w for w in data['widgets']}
        self.assertEqual(widgets['Desviación por cuenta analítica']['compare_datasets'][0]['data'], [1000.0])
        self.assertFalse(widgets['Margen operativo NeoData por semana'].get('compare_datasets'))

    def test_upgrade_v12(self):
        """La migración quita el combinado, acomoda los existentes y agrega los nuevos sin duplicar."""
        new = [item['name'] for item in WEEK_REPORT['widgets'] if item.get('since')]
        self.dashboard.widget_ids.filtered(lambda w: w.name in new).unlink()
        combined = self.dashboard.widget_ids.filtered(lambda w: w.name == 'Balance de costos por partida')
        self.env['business.dashboard.widget'].create({
            'dashboard_id': self.dashboard.id, 'name': OLD_WEEK_NAMES[0], 'widget_type': 'section'})
        margin = self.dashboard.widget_ids.filtered(lambda w: w.name == 'Margen operativo al momento – proyectos')
        margin.write({'width': '6', 'sequence': 999})
        added = _upgrade_week_report_v12(self.env)
        self.assertEqual(len(added), len(new))
        self.assertFalse(_upgrade_week_report_v12(self.env), 'No se duplica')
        self.assertEqual((margin.width, margin.sequence), ('12', 170))
        self.assertEqual((combined.sequence, combined.width), (140, '4'))
        self.dashboard.invalidate_recordset(['widget_ids'])
        widgets = self._widgets()
        self.assertNotIn(OLD_WEEK_NAMES[0], widgets)
        self.assertIn('Balance financiero por proyecto', widgets)
