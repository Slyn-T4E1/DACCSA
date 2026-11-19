# -*- coding: utf-8 -*-
"""Pruebas de la Etapa 6 (app Tableros DACSA: tableros configurables)."""
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBusinessDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.user_a = env['res.users'].create({'name': 'CCR Vendedor A', 'login': 'ccr_vendedor_a'})
        cls.user_b = env['res.users'].create({'name': 'CCR Vendedor B', 'login': 'ccr_vendedor_b'})
        Lead = env['crm.lead']
        cls.tag = 'CCRDASH'
        # 3 oportunidades de A (2 ganadas) y 1 de B, con monto y fechas conocidas
        cls.leads = Lead
        for user, amount, closed, won in ((cls.user_a, 100, date(2026, 3, 10), True),
                                          (cls.user_a, 200, date(2026, 4, 5), True),
                                          (cls.user_a, 50, date(2025, 6, 1), False),
                                          (cls.user_b, 400, date(2026, 3, 20), True)):
            lead = Lead.create({'name': cls.tag, 'type': 'opportunity', 'user_id': user.id,
                                'expected_revenue': amount})
            lead.write({'date_closed': closed})
            if won:
                lead.action_set_won()
                lead.write({'date_closed': closed})
            cls.leads |= lead
        model = env['ir.model']._get_id('crm.lead')
        Fields = env['ir.model.fields']
        cls.dashboard = env['business.dashboard'].create({'name': 'CCR Tablero'})
        cls.f_period = env['business.dashboard.filter'].create({
            'dashboard_id': cls.dashboard.id, 'name': 'Periodo', 'filter_type': 'date',
            'field_name': 'date_closed', 'default_period': 'all'})
        cls.f_user = env['business.dashboard.filter'].create({
            'dashboard_id': cls.dashboard.id, 'name': 'Vendedor', 'filter_type': 'many2one',
            'field_name': 'user_id', 'comodel_id': env['ir.model']._get_id('res.users'), 'multiple': True})
        base = "[('name', '=', '%s')]" % cls.tag
        Widget = env['business.dashboard.widget']
        cls.kpi_total = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Monto', 'code': 'monto', 'widget_type': 'kpi',
            'model_id': model, 'domain': base,
            'measure_ids': [(0, 0, {'name': 'Monto', 'code': 'monto', 'aggregate': 'sum',
                                    'field_id': Fields._get('crm.lead', 'expected_revenue').id})]})
        cls.kpi_won = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Ganadas', 'code': 'ganadas', 'widget_type': 'kpi',
            'model_id': model, 'domain': base[:-1] + ", ('won_status', '=', 'won')]",
            'measure_ids': [(0, 0, {'name': 'Ganadas', 'code': 'ganadas', 'aggregate': 'count'})]})
        cls.kpi_count = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Todas', 'code': 'todas', 'widget_type': 'kpi',
            'model_id': model, 'domain': base, 'hidden': True,
            'measure_ids': [(0, 0, {'name': 'Todas', 'code': 'todas', 'aggregate': 'count'})]})
        cls.kpi_ratio = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': '% ganadas', 'code': 'ratio', 'widget_type': 'kpi',
            'formula': 'div(ganadas, todas)', 'value_format': 'percent',
            'color_mode': 'threshold', 'threshold': '0.9'})
        cls.table = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Por vendedor', 'widget_type': 'table',
            'model_id': model, 'domain': base, 'groupby_field_id': Fields._get('crm.lead', 'user_id').id,
            'measure_ids': [
                (0, 0, {'sequence': 1, 'name': 'Monto', 'code': 'monto', 'aggregate': 'sum',
                        'field_id': Fields._get('crm.lead', 'expected_revenue').id}),
                (0, 0, {'sequence': 2, 'name': 'Ganado', 'code': 'ganado', 'aggregate': 'sum',
                        'field_id': Fields._get('crm.lead', 'expected_revenue').id,
                        'extra_domain': "[('won_status', '=', 'won')]"}),
                (0, 0, {'sequence': 3, 'name': '% del total', 'code': 'pct',
                        'formula': 'div(monto, total_kpi)', 'value_format': 'percent'}),
            ]})
        cls.chart = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Por mes', 'widget_type': 'chart',
            'model_id': model, 'domain': base, 'groupby_field_id': Fields._get('crm.lead', 'date_closed').id,
            'groupby_interval': 'month',
            'measure_ids': [(0, 0, {'name': 'Monto', 'code': 'monto', 'aggregate': 'sum',
                                    'field_id': Fields._get('crm.lead', 'expected_revenue').id})]})
        cls.listing = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Listado', 'widget_type': 'list', 'model_id': model,
            'domain': base, 'list_fields': 'name, user_id, expected_revenue', 'list_order': 'expected_revenue desc'})
        # Indicador que usa la tabla en su fórmula (total_kpi)
        Widget.create({'dashboard_id': cls.dashboard.id, 'name': 'Total', 'code': 'total_kpi',
                       'widget_type': 'kpi', 'formula': 'monto', 'hidden': True})

    def _data(self, values=None):
        data = self.dashboard.get_dashboard_data(values or {})
        return {w['id']: w for w in data['widgets']}, data

    def test_kpis_and_formula(self):
        widgets, data = self._data()
        self.assertFalse([w['error'] for w in widgets.values() if w['error']])
        self.assertEqual(widgets[self.kpi_total.id]['value'], 750)
        self.assertEqual(widgets[self.kpi_won.id]['value'], 3)
        self.assertAlmostEqual(widgets[self.kpi_ratio.id]['value'], 0.75)
        self.assertEqual(widgets[self.kpi_ratio.id]['state'], 'bad')      # 75 % < 90 %
        self.assertNotIn(self.kpi_count.id, widgets, 'Los ocultos no se muestran')
        self.assertEqual(len(data['filters']), 2)

    def test_filters(self):
        values = {str(self.f_user.id): [self.user_a.id],
                  str(self.f_period.id): {'preset': 'custom', 'from': '2026-01-01', 'to': '2026-12-31'}}
        widgets, _data = self._data(values)
        self.assertEqual(widgets[self.kpi_total.id]['value'], 300)        # A, cerradas en 2026
        widget_map = self.env['business.dashboard.widget.filter'].create({
            'widget_id': self.kpi_total.id, 'filter_id': self.f_period.id, 'field_path': False})
        widgets, _data = self._data(values)
        self.assertEqual(widgets[self.kpi_total.id]['value'], 350, 'Sin periodo: todas las de A')
        widget_map.unlink()

    def test_table_chart_list(self):
        widgets, _data = self._data()
        table = widgets[self.table.id]
        rows = {row['label']: row['cells'] for row in table['rows']}
        self.assertEqual([c['value'] for c in rows['CCR Vendedor A']][:2], [350, 300])
        self.assertAlmostEqual(rows['CCR Vendedor B'][2]['value'], 400 / 750)
        self.assertEqual(table['total']['cells'][0]['value'], 750)
        chart = widgets[self.chart.id]
        self.assertEqual(sum(chart['datasets'][0]['data']), 750)
        self.assertEqual(len(chart['labels']), 3)                           # jun 2025, mar 2026, abr 2026
        listing = widgets[self.listing.id]
        self.assertEqual(listing['records'][0]['cells'][2], 400)

    def test_drilldown(self):
        action = self.table.get_drilldown_action({}, group_key=self.user_b.id)
        self.assertEqual(self.env['crm.lead'].search(action['domain']), self.leads.filtered(
            lambda l: l.user_id == self.user_b))
        measure = self.table.measure_ids.filtered(lambda m: m.code == 'ganado')
        action = self.table.get_drilldown_action({}, group_key=self.user_a.id, measure_id=measure.id)
        self.assertEqual(len(self.env['crm.lead'].search(action['domain'])), 2)
        action = self.chart.get_drilldown_action({}, group_key='2026-03-01')
        self.assertEqual(len(self.env['crm.lead'].search(action['domain'])), 2)

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.kpi_total.domain = "[('no_existe', '=', 1)]"
        with self.assertRaises(ValidationError):
            self.listing.list_fields = 'name, campo_falso'
        self.kpi_ratio.formula = 'div(ganadas, no_existe)'
        widgets, _data = self._data()
        self.assertTrue(widgets[self.kpi_ratio.id]['error'])

    def test_default_dashboards(self):
        """Los tableros de fábrica existen y calculan sin errores."""
        for xmlid in ('dashboard_commercial', 'dashboard_commercial_lists', 'dashboard_week_report'):
            dashboard = self.env.ref('custom_business_reports.%s' % xmlid)
            data = dashboard.get_dashboard_data({})
            errors = [(w['title'], w['error']) for w in data['widgets'] if w['error']]
            self.assertFalse(errors, xmlid)
        names = [d['name'] for d in self.env['business.dashboard'].get_dashboard_list()]
        self.assertIn('Reporte semanal Dirección', names)

    def test_visibility_by_group(self):
        """Cada usuario ve solo los tableros de sus grupos y no los configura."""
        salesman = self.env['res.users'].create({
            'name': 'CCR Solo ventas', 'login': 'ccr_solo_ventas',
            'group_ids': [(6, 0, [self.env.ref('sales_team.group_sale_salesman').id])]})
        names = [d['name'] for d in self.env['business.dashboard'].with_user(salesman).get_dashboard_list()]
        self.assertIn('Seguimiento comercial', names)
        self.assertNotIn('Reporte semanal Dirección', names)
        dashboard = self.env.ref('custom_business_reports.dashboard_commercial').with_user(salesman)
        self.assertFalse(dashboard.get_dashboard_data({})['can_edit'])
