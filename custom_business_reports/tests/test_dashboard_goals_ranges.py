# -*- coding: utf-8 -*-
"""Pruebas de 19.0.8.0.0: tabla con grupos en columnas, metas de venta
mensuales (medida de otro modelo) y rangos de antigüedad."""
from datetime import date, timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.custom_business_reports.dashboard_defaults import _ensure_widgets


@tagged('post_install', '-at_install')
class TestDashboardGoalsRanges(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.tag = 'CCRV8'
        Lead = env['crm.lead']
        today = fields.Date.context_today(Lead)
        cls.today = today
        cls.leads = Lead
        # Ganadas: 100 y 200 en marzo 2026, 400 en abril 2026. Abiertas con días desde el cierre
        # previsto: 10, 45 y 200 días (para los rangos).
        for amount, closed, won in ((100, date(2026, 3, 10), True), (200, date(2026, 3, 20), True),
                                    (400, date(2026, 4, 5), True), (10, today - timedelta(days=10), False),
                                    (20, today - timedelta(days=45), False),
                                    (30, today - timedelta(days=200), False)):
            lead = Lead.create({'name': cls.tag, 'type': 'opportunity', 'expected_revenue': amount})
            if won:
                lead.action_set_won()
            lead.write({'date_closed': closed})
            cls.leads |= lead
        Goal = env['business.sales.goal']
        Goal.search([]).unlink()
        cls.goals = Goal.create([
            {'date': '2026-03-15', 'amount': 250},      # se guarda como 1 de marzo
            {'date': '2026-04-01', 'amount': 500},
            {'date': '2026-05-01', 'amount': 600},      # mes sin venta
        ])
        model = env['ir.model']._get_id('crm.lead')
        Fields = env['ir.model.fields']
        cls.dashboard = env['business.dashboard'].create({'name': 'CCR v8'})
        cls.f_period = env['business.dashboard.filter'].create({
            'dashboard_id': cls.dashboard.id, 'name': 'Periodo', 'filter_type': 'date',
            'field_name': 'date_closed', 'default_period': 'custom'})
        won = "[('name', '=', '%s'), ('won_status', '=', 'won')]" % cls.tag
        revenue = Fields._get('crm.lead', 'expected_revenue').id
        Widget = env['business.dashboard.widget']
        cls.kpi_sale = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Venta', 'code': 'venta', 'widget_type': 'kpi',
            'model_id': model, 'domain': won,
            'measure_ids': [(0, 0, {'name': 'Venta', 'code': 'venta', 'aggregate': 'sum', 'field_id': revenue})]})
        cls.kpi_goal = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Meta', 'code': 'meta', 'widget_type': 'kpi',
            'model_id': env['ir.model']._get_id('business.sales.goal'),
            'filter_map_ids': [(0, 0, {'filter_id': cls.f_period.id, 'field_path': 'date'})],
            'measure_ids': [(0, 0, {'name': 'Meta', 'code': 'meta', 'aggregate': 'sum',
                                    'field_id': Fields._get('business.sales.goal', 'amount').id})]})
        cls.kpi_progress = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Avance', 'code': 'avance', 'widget_type': 'kpi',
            'formula': 'div(venta, meta)', 'value_format': 'percent'})
        cls.chart = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Venta vs meta', 'widget_type': 'chart',
            'model_id': model, 'domain': won, 'groupby_field_id': Fields._get('crm.lead', 'date_closed').id,
            'groupby_interval': 'month',
            'measure_ids': [
                (0, 0, {'sequence': 1, 'name': 'Venta', 'code': 'venta', 'aggregate': 'sum', 'field_id': revenue}),
                (0, 0, {'sequence': 2, 'name': 'Meta', 'code': 'meta', 'aggregate': 'sum',
                        'source_model_id': env['ir.model']._get_id('business.sales.goal'),
                        'source_groupby_field': 'date', 'series_type': 'line',
                        'field_id': Fields._get('business.sales.goal', 'amount').id}),
            ]})
        cls.month_table = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Mes a mes', 'widget_type': 'table',
            'model_id': model, 'domain': "[('name', '=', '%s')]" % cls.tag, 'table_transpose': True,
            'groupby_field_id': Fields._get('crm.lead', 'date_closed').id, 'groupby_interval': 'month',
            'measure_ids': [
                (0, 0, {'sequence': 1, 'name': 'Todas', 'code': 'todas', 'aggregate': 'count'}),
                (0, 0, {'sequence': 2, 'name': 'Ganadas', 'code': 'ganadas', 'aggregate': 'count',
                        'extra_domain': "[('won_status', '=', 'won')]"}),
                (0, 0, {'sequence': 3, 'name': '% ganadas', 'code': 'pct', 'formula': 'div(ganadas, todas)',
                        'value_format': 'percent'}),
            ]})
        cls.ranges = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Antigüedad', 'widget_type': 'chart',
            'model_id': model, 'domain': "[('name', '=', '%s'), ('won_status', '=', 'pending')]" % cls.tag,
            'range_field_id': Fields._get('crm.lead', 'date_closed').id, 'range_bounds': '30,60,90,180',
            'filter_map_ids': [(0, 0, {'filter_id': cls.f_period.id, 'field_path': False})],
            'measure_ids': [
                (0, 0, {'sequence': 1, 'name': 'Oportunidades', 'code': 'n', 'aggregate': 'count'}),
                (0, 0, {'sequence': 2, 'name': 'Monto', 'code': 'monto', 'aggregate': 'sum', 'field_id': revenue,
                        'series_type': 'line', 'right_axis': True, 'value_format': 'monetary'}),
            ]})

    def _data(self, date_from='2026-01-01', date_to='2026-12-31'):
        values = {str(self.f_period.id): {'preset': 'custom', 'from': date_from, 'to': date_to}}
        data = self.dashboard.get_dashboard_data(values)
        self.assertFalse([(w['title'], w['error']) for w in data['widgets'] if w['error']])
        return {w['id']: w for w in data['widgets']}, values

    def test_goal_model(self):
        self.assertEqual(self.goals[0].date, date(2026, 3, 1), 'La meta se guarda el día 1 del mes')
        self.assertIn('2026', self.goals[0].name)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self.env['business.sales.goal'].create({'date': '2026-03-28', 'amount': 1})
            self.env.flush_all()

    def test_goal_kpis(self):
        widgets, _values = self._data('2026-03-01', '2026-04-30')
        self.assertEqual(widgets[self.kpi_sale.id]['value'], 700)
        self.assertEqual(widgets[self.kpi_goal.id]['value'], 750)
        self.assertAlmostEqual(widgets[self.kpi_progress.id]['value'], 700 / 750)
        widgets, _values = self._data('2026-01-01', '2026-12-31')
        self.assertEqual(widgets[self.kpi_goal.id]['value'], 1350)

    def test_chart_sales_vs_goal(self):
        widgets, values = self._data()
        chart = widgets[self.chart.id]
        self.assertEqual(chart['keys'], ['2026-03-01', '2026-04-01', '2026-05-01'],
                         'El mes con meta y sin venta también aparece')
        sale, goal = chart['datasets']
        self.assertEqual(sale['data'], [300, 400, 0])
        self.assertEqual(goal['data'], [250, 500, 600])
        self.assertEqual(goal['series_type'], 'line')
        # Detalle de la meta: abre las metas de ese mes
        action = self.chart.get_drilldown_action(values, group_key='2026-04-01', measure_id=goal['measure_id'])
        self.assertEqual(action['res_model'], 'business.sales.goal')
        self.assertEqual(self.env['business.sales.goal'].search(action['domain']), self.goals[1])

    def test_transposed_table(self):
        widgets, values = self._data('2026-03-01', '2026-04-30')
        table = widgets[self.month_table.id]
        self.assertTrue(table['transposed'])
        self.assertEqual([c['id'] for c in table['columns']], ['2026-03-01', '2026-04-01', '__total__'])
        self.assertEqual([r['label'] for r in table['rows']], ['Todas', 'Ganadas', '% ganadas'])
        todas, ganadas, pct = table['rows']
        self.assertEqual([c['value'] for c in todas['cells']], [2, 1, 3])
        self.assertEqual([c['value'] for c in ganadas['cells']], [2, 1, 3])
        self.assertEqual(pct['cells'][-1]['value'], 1.0)
        self.assertEqual(pct['format'], 'percent')
        # Clic en una celda: mes de la columna + medida del renglón
        click = ganadas['cells'][1]['click']
        action = self.month_table.get_drilldown_action(values, **click)
        self.assertEqual(len(self.env['crm.lead'].search(action['domain'])), 1)

    def test_age_ranges(self):
        widgets, values = self._data()
        chart = widgets[self.ranges.id]
        self.assertEqual(chart['labels'], ['0–30 días', '31–60 días', '61–90 días', '91–180 días',
                                           'Más de 180 días'])
        count, amount = chart['datasets']
        self.assertEqual(count['data'], [1, 1, 0, 0, 1])
        self.assertEqual(amount['data'], [10, 20, 0, 0, 30])
        self.assertTrue(amount['right_axis'])
        self.assertEqual(chart['right_format'], 'monetary')
        action = self.ranges.get_drilldown_action(values, group_key='r4')
        self.assertEqual(self.env['crm.lead'].search(action['domain']).mapped('expected_revenue'), [30])

    def test_ensure_new_widgets(self):
        """La migración agrega los elementos nuevos al tablero comercial sin duplicarlos."""
        dashboard = self.env.ref('custom_business_reports.dashboard_commercial')
        names = ['Meta de venta', 'Avance vs meta', 'Invitaciones a cotizar, mes a mes',
                 'Venta por mes de cierre vs meta mensual', 'Pipeline abierto por antigüedad',
                 'Antigüedad del pipeline enviado', 'Pipeline enviado por rango de días']
        self.assertTrue(set(names) <= set(dashboard.widget_ids.mapped('name')))
        dashboard.widget_ids.filtered(lambda w: w.name in names).unlink()
        added = _ensure_widgets(self.env, since='19.0.8.0.0')
        self.assertEqual(len([a for a in added if a.startswith(dashboard.name)]), 7)
        self.assertFalse(_ensure_widgets(self.env, since='19.0.8.0.0'), 'No se duplican')
        data = dashboard.get_dashboard_data({})
        self.assertFalse([(w['title'], w['error']) for w in data['widgets'] if w['error']])
        order = [w['title'] for w in data['widgets']]
        self.assertLess(order.index('Avance vs meta'), order.index('Invitaciones a cotizar por mes'))
        self.assertGreater(order.index('Antigüedad del pipeline enviado'),
                           order.index('Embudo por segmento (periodo seleccionado)'))
