# -*- coding: utf-8 -*-
"""Pruebas de 19.0.9.0.0: listados con #, total, resaltado y grupos; valores de
indicadores en textos; segundo valor; fechas relativas en dominios; semanas
creación→cierre y el nuevo "Listados comerciales"."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.custom_business_reports.dashboard_defaults import OLD_LIST_NAMES, _upgrade_commercial_lists


@tagged('post_install', '-at_install')
class TestDashboardLists(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.tag = 'CCRV9'
        Lead = env['crm.lead']
        cls.stage_a = env['crm.stage'].create({'name': 'CCR Etapa A', 'sequence': 1})
        cls.stage_b = env['crm.stage'].create({'name': 'CCR Etapa B', 'sequence': 2})
        cls.leads = Lead.create([
            {'name': cls.tag, 'type': 'opportunity', 'expected_revenue': 100, 'stage_id': cls.stage_a.id},
            {'name': cls.tag, 'type': 'opportunity', 'expected_revenue': 300, 'stage_id': cls.stage_b.id},
            {'name': cls.tag, 'type': 'opportunity', 'expected_revenue': 200, 'stage_id': cls.stage_a.id},
        ])
        # Antigüedad conocida: 10, 400 y 40 días
        now = fields.Datetime.now()
        for lead, days in zip(cls.leads, (10, 400, 40)):
            env.cr.execute('UPDATE crm_lead SET create_date = %s WHERE id = %s', (now - timedelta(days=days), lead.id))
        cls.leads.invalidate_recordset(['create_date'])
        model = env['ir.model']._get_id('crm.lead')
        cls.dashboard = env['business.dashboard'].create({'name': 'CCR v9'})
        base = "[('name', '=', '%s')]" % cls.tag
        Widget = env['business.dashboard.widget']
        Fields = env['ir.model.fields']
        cls.kpi_count = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Cuántas', 'code': 'n', 'widget_type': 'kpi',
            'model_id': model, 'domain': base, 'value_format': 'integer', 'secondary_code': 'monto',
            'subtitle': 'monto {monto} · {n} leads',
            'measure_ids': [(0, 0, {'name': 'N', 'code': 'n', 'aggregate': 'count'})]})
        cls.kpi_amount = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Monto', 'code': 'monto', 'widget_type': 'kpi',
            'model_id': model, 'domain': base, 'value_format': 'monetary', 'hidden': True,
            'measure_ids': [(0, 0, {'name': 'Monto', 'code': 'monto', 'aggregate': 'sum',
                                    'field_id': Fields._get('crm.lead', 'expected_revenue').id})]})
        cls.kpi_old = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Viejas', 'code': 'viejas', 'widget_type': 'kpi',
            'model_id': model, 'value_format': 'integer',
            'domain': "[('name', '=', '%s'), ('create_date', '<', (context_today() - "
                      "relativedelta(days=180)).strftime('%%Y-%%m-%%d'))]" % cls.tag,
            'measure_ids': [(0, 0, {'name': 'N', 'code': 'viejas', 'aggregate': 'count'})]})
        cls.listing = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Listado de {n}', 'widget_type': 'list', 'model_id': model,
            'domain': base, 'list_fields': 'name, report_age_days, expected_revenue',
            'list_order': 'expected_revenue desc', 'limit': 2, 'list_show_number': True, 'list_show_total': True,
            'list_highlight': 'report_age_days > 365'})
        cls.grouped = Widget.create({
            'dashboard_id': cls.dashboard.id, 'name': 'Por etapa', 'widget_type': 'list', 'model_id': model,
            'domain': base, 'list_fields': 'name, expected_revenue', 'list_order': 'expected_revenue desc',
            'list_group_field': 'stage_id', 'limit': 10})

    def _data(self):
        data = self.dashboard.get_dashboard_data({})
        self.assertFalse([(w['title'], w['error']) for w in data['widgets'] if w['error']])
        return {w['id']: w for w in data['widgets']}

    def test_kpi_texts_and_relative_domain(self):
        widgets = self._data()
        kpi = widgets[self.kpi_count.id]
        self.assertEqual(kpi['value'], 3)
        self.assertEqual(kpi['secondary'], '$600')
        self.assertEqual(kpi['subtitle'], 'monto $600 · 3 leads')
        self.assertEqual(widgets[self.kpi_old.id]['value'], 1, 'Solo la de 400 días')
        self.assertEqual(widgets[self.listing.id]['title'], 'Listado de 3')

    def test_list_options(self):
        listing = self._data()[self.listing.id]
        self.assertEqual(listing['count'], 3)
        self.assertEqual(listing['shown'], 2)
        self.assertEqual([r['number'] for r in listing['records']], [1, 2])
        self.assertEqual(listing['records'][0]['cells'][2], 300)
        self.assertEqual(listing['records'][0]['red'], [1], 'La de 400 días va en rojo')
        self.assertEqual(listing['records'][1]['red'], [])
        self.assertEqual(listing['total'], ['', '', 600], 'El total es de todos los registros, no solo de los 2')
        with self.assertRaises(ValidationError):
            self.listing.list_highlight = 'no es regla'

    def test_grouped_list(self):
        grouped = self._data()[self.grouped.id]
        rows = grouped['records']
        self.assertTrue(grouped['grouped'])
        self.assertEqual([(r.get('group'), r.get('count')) for r in rows if r.get('group')],
                         [('CCR Etapa A', 2), ('CCR Etapa B', 1)])
        self.assertEqual([r['cells'][1] for r in rows if not r.get('group')], [200, 100, 300])

    def test_close_weeks(self):
        lead = self.leads[0]
        lead.date_closed = lead.create_date + timedelta(days=21)
        self.assertEqual(lead.report_close_weeks, 3.0)
        lead.date_closed = lead.create_date + timedelta(days=10)
        self.assertEqual(lead.report_close_weeks, 1.4)

    def test_commercial_lists(self):
        """El tablero nuevo calcula sin errores y la migración reemplaza los listados anteriores."""
        dashboard = self.env.ref('custom_business_reports.dashboard_commercial_lists')
        data = dashboard.get_dashboard_data({})
        self.assertFalse([(w['title'], w['error']) for w in data['widgets'] if w['error']])
        titles = [w['title'] for w in data['widgets']]
        for name in ('Proyectos ganados', 'Ganados Sin Recompra', 'Perdidos por monto', 'Cancelados por monto',
                     'En pausa por monto', 'Cotizaciones enviadas por monto', 'Leads de los últimos 3 meses'):
            self.assertIn(name, titles)
        self.assertEqual(titles[-1], 'Oportunidades lentas (más tiempo sin movimiento)')
        # Simula un tablero de la versión anterior y migra
        dashboard.widget_ids.filtered(lambda w: w.widget_type != 'list' or 'lentas' not in w.name).unlink()
        model = self.env['ir.model']._get_id('crm.lead')
        for name in OLD_LIST_NAMES:
            self.env['business.dashboard.widget'].create({
                'dashboard_id': dashboard.id, 'name': name, 'widget_type': 'list', 'model_id': model,
                'list_fields': 'name'})
        dashboard.widget_ids.filtered(lambda w: 'lentas' in w.name).sequence = 60
        added = _upgrade_commercial_lists(self.env)
        self.assertTrue(len(added) > 40)
        dashboard.invalidate_recordset(['widget_ids'])
        data = dashboard.get_dashboard_data({})
        titles = [w['title'] for w in data['widgets']]
        self.assertFalse(set(titles) & (set(OLD_LIST_NAMES) - {'Proyectos en pausa', 'Proyectos cancelados'}))
        self.assertEqual(titles[-1], 'Oportunidades lentas (más tiempo sin movimiento)')
        self.assertEqual(titles[0], 'Proyectos ganados')
        self.assertFalse(_upgrade_commercial_lists(self.env), 'Correrla otra vez no duplica')
