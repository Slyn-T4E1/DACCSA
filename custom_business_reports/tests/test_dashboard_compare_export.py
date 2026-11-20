# -*- coding: utf-8 -*-
"""Pruebas de 19.0.11.0.0: comparativo en los tableros, exportar a Excel y PDF y
menús dentro de la app Tableros DACSA."""
import io
import zipfile
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDashboardCompareExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.tag = 'CCRV11'
        cls.user_a = env['res.users'].create({'name': 'CCR11 A', 'login': 'ccr11_a'})
        cls.user_b = env['res.users'].create({'name': 'CCR11 B', 'login': 'ccr11_b'})
        Lead = env['crm.lead']
        # 2031: 100 (ene, A) + 300 (mar, B) · 2030: 50 (ene, A) + 200 (feb, A)
        for amount, closed, user in ((100, date(2031, 1, 10), cls.user_a), (300, date(2031, 3, 5), cls.user_b),
                                     (50, date(2030, 1, 20), cls.user_a), (200, date(2030, 2, 3), cls.user_a)):
            lead = Lead.create({'name': cls.tag, 'type': 'opportunity', 'expected_revenue': amount,
                                'user_id': user.id})
            lead.action_set_won()
            lead.write({'date_closed': closed})
        model = env['ir.model']._get_id('crm.lead')
        Fields = env['ir.model.fields']
        revenue = Fields._get('crm.lead', 'expected_revenue').id
        cls.dashboard = env['business.dashboard'].create({'name': 'CCR v11'})
        cls.period = env['business.dashboard.filter'].create({
            'dashboard_id': cls.dashboard.id, 'name': 'Periodo', 'filter_type': 'date', 'field_name': 'date_closed',
            'default_period': 'custom'})
        cls.seller = env['business.dashboard.filter'].create({
            'dashboard_id': cls.dashboard.id, 'name': 'Vendedor', 'filter_type': 'many2one', 'field_name': 'user_id',
            'comodel_id': env['ir.model']._get_id('res.users'), 'multiple': False})
        base = "[('name', '=', '%s')]" % cls.tag
        Widget = env['business.dashboard.widget']
        cls.kpi = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Venta', 'code': 'venta', 'widget_type': 'kpi',
            'model_id': model, 'domain': base, 'value_format': 'monetary',
            'measure_ids': [(0, 0, {'name': 'Venta', 'code': 'venta', 'aggregate': 'sum', 'field_id': revenue})]})
        cls.chart = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Venta por mes', 'widget_type': 'chart', 'model_id': model,
            'domain': base, 'groupby_field_id': Fields._get('crm.lead', 'date_closed').id, 'groupby_interval': 'month',
            'measure_ids': [(0, 0, {'name': 'Venta', 'code': 'venta', 'aggregate': 'sum', 'field_id': revenue})]})
        cls.table = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Por mes', 'widget_type': 'table', 'model_id': model,
            'domain': base, 'groupby_field_id': Fields._get('crm.lead', 'date_closed').id, 'groupby_interval': 'month',
            'measure_ids': [(0, 0, {'name': 'Venta', 'code': 'venta', 'aggregate': 'sum', 'field_id': revenue,
                                    'value_format': 'monetary'})]})
        cls.today_kpi = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'A hoy', 'code': 'hoy', 'widget_type': 'kpi',
            'model_id': model, 'domain': base, 'value_format': 'monetary',
            'filter_map_ids': [(0, 0, {'filter_id': cls.period.id, 'field_path': False})],
            'measure_ids': [(0, 0, {'name': 'Total', 'code': 'hoy', 'aggregate': 'sum', 'field_id': revenue})]})
        cls.listing = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Listado', 'widget_type': 'list', 'model_id': model,
            'domain': base, 'list_fields': 'date_closed:Cierre, user_id, expected_revenue:Monto',
            'list_show_total': True, 'list_show_number': True})
        cls.values = {str(cls.period.id): {'preset': 'custom', 'from': '2031-01-01', 'to': '2031-12-31'}}

    def _widgets(self, compare):
        data = self.dashboard.get_dashboard_data(self.values, compare)
        self.assertFalse([(w['title'], w['error']) for w in data['widgets'] if w['error']])
        return {w['id']: w for w in data['widgets']}, data

    def test_compare_previous_year(self):
        widgets, data = self._widgets({'mode': 'previous_year'})
        self.assertEqual(data['compare']['label'][-4:], '2030')
        kpi = widgets[self.kpi.id]
        self.assertEqual(kpi['value'], 400)
        self.assertEqual(kpi['compare']['value'], 250)
        self.assertAlmostEqual(kpi['compare']['delta'], 0.6)
        chart = widgets[self.chart.id]
        self.assertEqual(chart['keys'], ['2031-01-01', '2031-03-01'])
        self.assertEqual(chart['compare_datasets'][0]['data'], [50, 0], 'Enero contra enero; marzo 2030 sin venta')
        rows = {row['key']: row for row in widgets[self.table.id]['rows']}
        self.assertEqual(rows['2031-01-01']['compare'], [50])
        self.assertIsNone(rows['2031-03-01']['compare'])
        self.assertEqual(widgets[self.table.id]['total']['compare'], [250])
        self.assertNotIn('compare', widgets[self.today_kpi.id], 'Sin periodo no se compara: saldría igual')
        self.assertTrue(data['compare_options']['date'])
        self.assertEqual(data['compare_options']['records'][0]['filter_id'], self.seller.id)

    def test_compare_custom_and_record(self):
        widgets, data = self._widgets({'mode': 'custom', 'from': '2030-01-01', 'to': '2030-01-31'})
        self.assertEqual(widgets[self.kpi.id]['compare']['value'], 50)
        values = dict(self.values, **{str(self.seller.id): [self.user_a.id]})
        data = self.dashboard.get_dashboard_data(values, {'mode': 'record', 'filter_id': self.seller.id,
                                                          'record_id': self.user_b.id})
        kpi = next(w for w in data['widgets'] if w['id'] == self.kpi.id)
        self.assertEqual((kpi['value'], kpi['compare']['value']), (100, 300))
        self.assertEqual(data['compare']['label'], 'CCR11 B')
        # Sin comparativo completo no se compara
        data = self.dashboard.get_dashboard_data(self.values, {'mode': 'custom'})
        self.assertFalse(data['compare'])

    def test_export_xlsx(self):
        action = self.dashboard.export_xlsx(self.values, {'mode': 'previous_year'})
        self.assertEqual(action['type'], 'ir.actions.act_url')
        attachment = self.env['ir.attachment'].sudo().search([('res_model', '=', 'business.dashboard'),
                                                              ('res_id', '=', self.dashboard.id)], limit=1)
        self.assertTrue(attachment.name.endswith('.xlsx'))
        self.assertIn('access_token=', action['url'])
        with zipfile.ZipFile(io.BytesIO(attachment.raw)) as book:
            names = book.namelist()
            self.assertIn('xl/workbook.xml', names)
            self.assertEqual(len([n for n in names if n.startswith('xl/worksheets/sheet')]), 4)
            self.assertTrue([n for n in names if n.startswith('xl/charts/chart')], 'Gráfica nativa de Excel')

    def test_export_pdf(self):
        image = 'data:image/png;base64,iVBORw0KGgo='
        action = self.dashboard.export_pdf(self.values, {'mode': 'previous_year'}, {str(self.chart.id): image})
        attachment = self.env['ir.attachment'].sudo().search([('res_model', '=', 'business.dashboard'),
                                                              ('res_id', '=', self.dashboard.id)], limit=1)
        self.assertIn('/web/content/%s' % attachment.id, action['url'])
        html = attachment.raw.decode()
        self.assertIn('CCR v11', html)
        self.assertIn(image, html)
        self.assertIn('Comparativo', html)
        self.assertIn('Venta por mes', html)

    def test_salesman_can_export(self):
        """Un usuario que solo ve el tablero también exporta (el adjunto se crea con permisos propios)."""
        salesman = self.env['res.users'].create({
            'name': 'CCR11 vendedor', 'login': 'ccr11_vendedor',
            'group_ids': [(6, 0, [self.env.ref('sales_team.group_sale_salesman').id])]})
        dashboard = self.env.ref('custom_business_reports.dashboard_commercial').with_user(salesman)
        self.assertEqual(dashboard.export_xlsx({}, {'mode': 'previous_year'})['type'], 'ir.actions.act_url')

    def test_menus_in_dashboard_app(self):
        root = self.env.ref('custom_business_reports.menu_business_dashboard_root')
        for xmlid in ('menu_business_reports_root', 'menu_business_list_won', 'menu_week_report_weeks',
                      'menu_week_report_dashboard', 'menu_week_report_projects', 'menu_crm_lead_segment_rule',
                      'menu_budget_post_partida', 'menu_business_sales_goal_dashboard'):
            menu = self.env.ref('custom_business_reports.%s' % xmlid)
            self.assertTrue(menu.parent_path.startswith('%s/' % root.id), xmlid)
        self.assertFalse(self.env.ref('custom_business_reports.menu_business_sales_goal_crm',
                                      raise_if_not_found=False))
        config = self.env.ref('custom_business_reports.menu_business_dashboard_config_root')
        self.assertFalse(config.group_ids)
