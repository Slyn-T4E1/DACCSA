# -*- coding: utf-8 -*-
"""Pruebas de 19.0.10.0.0: medidas acumuladas y sin periodo, segmento SR/R y el
nuevo "Seguimiento comercial" (resumen, embudo Totales / SR / R, venta por
trimestre vs meta acumulada) con su migración."""
from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.custom_business_reports.dashboard_defaults import (
    COMMERCIAL, OLD_COMMERCIAL_SUBTITLES, V10, _available, _upgrade_commercial_v10)


@tagged('post_install', '-at_install')
class TestCommercialV10(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.tag = 'CCRV10'
        Lead = env['crm.lead']
        # Ganadas: 100 en ene 2031, 200 en may 2031, 300 en nov 2031 y 50 en 2030
        cls.leads = Lead
        for amount, closed in ((100, date(2031, 1, 10)), (200, date(2031, 5, 10)), (300, date(2031, 11, 10)),
                               (50, date(2030, 6, 1))):
            lead = Lead.create({'name': cls.tag, 'type': 'opportunity', 'expected_revenue': amount})
            lead.action_set_won()
            lead.write({'date_closed': closed})
            cls.leads |= lead
        env['business.sales.goal'].search([]).unlink()
        env['business.sales.goal'].create([{'date': '2031-%02d-01' % month, 'amount': 100} for month in range(1, 13)])
        model = env['ir.model']._get_id('crm.lead')
        Fields = env['ir.model.fields']
        cls.dashboard = env['business.dashboard'].create({'name': 'CCR v10'})
        cls.period = env['business.dashboard.filter'].create({
            'dashboard_id': cls.dashboard.id, 'name': 'Periodo', 'filter_type': 'date', 'field_name': 'date_closed',
            'default_period': 'custom'})
        revenue = Fields._get('crm.lead', 'expected_revenue').id
        cls.chart = env['business.dashboard.widget'].create({
            'dashboard_id': cls.dashboard.id, 'name': 'Trimestres', 'widget_type': 'chart', 'model_id': model,
            'domain': "[('name', '=', '%s')]" % cls.tag, 'groupby_interval': 'quarter',
            'groupby_field_id': Fields._get('crm.lead', 'date_closed').id,
            'measure_ids': [
                (0, 0, {'sequence': 1, 'name': 'Venta', 'code': 'venta', 'aggregate': 'sum', 'field_id': revenue}),
                (0, 0, {'sequence': 2, 'name': 'Acumulado', 'code': 'acum', 'aggregate': 'sum', 'field_id': revenue,
                        'cumulative': True}),
                (0, 0, {'sequence': 3, 'name': 'Meta acumulada', 'code': 'meta', 'aggregate': 'sum',
                        'cumulative': True, 'source_model_id': env['ir.model']._get_id('business.sales.goal'),
                        'source_groupby_field': 'date',
                        'field_id': Fields._get('business.sales.goal', 'amount').id}),
            ]})
        cls.table = env['business.dashboard.widget'].create({
            'dashboard_id': cls.dashboard.id, 'name': 'Con histórico', 'widget_type': 'table', 'model_id': model,
            'domain': "[('name', '=', '%s')]" % cls.tag, 'table_transpose': True,
            'groupby_field_id': Fields._get('crm.lead', 'report_segment_group').id,
            'measure_ids': [
                (0, 0, {'sequence': 1, 'name': 'Del año', 'code': 'anio', 'aggregate': 'count'}),
                (0, 0, {'sequence': 2, 'name': 'Todos', 'code': 'todos', 'aggregate': 'count',
                        'ignore_period': True}),
            ]})

    def _data(self):
        values = {str(self.period.id): {'preset': 'custom', 'from': '2031-01-01', 'to': '2031-12-31'}}
        data = self.dashboard.get_dashboard_data(values)
        self.assertFalse([(w['title'], w['error']) for w in data['widgets'] if w['error']])
        return {w['id']: w for w in data['widgets']}, values

    def test_cumulative(self):
        widgets, _values = self._data()
        chart = widgets[self.chart.id]
        self.assertEqual(chart['keys'], ['2031-01-01', '2031-04-01', '2031-07-01', '2031-10-01'])
        venta, acum, meta = chart['datasets']
        self.assertEqual(venta['data'], [100, 200, 0, 300])
        self.assertEqual(acum['data'], [100, 300, 300, 600])
        self.assertEqual(meta['data'], [300, 600, 900, 1200])

    def test_ignore_period_and_segment_group(self):
        self.assertEqual(set(self.leads.mapped('report_segment_group')), {'sin_recompra'})
        widgets, values = self._data()
        table = widgets[self.table.id]
        rows = {row['key']: [cell['value'] for cell in row['cells']] for row in table['rows']}
        self.assertEqual(rows['anio'][-1], 3)
        self.assertEqual(rows['todos'][-1], 4, 'Sin periodo cuenta también la de 2030')
        measure = self.table.measure_ids.filtered(lambda m: m.code == 'todos')
        action = self.table.get_drilldown_action(values, group_key='sin_recompra', measure_id=measure.id)
        self.assertEqual(len(self.env['crm.lead'].search(action['domain'])), 4)
        self.leads[0].report_segment = 'recompra'
        self.assertEqual(self.leads[0].report_segment_group, 'recompra')

    def test_commercial_dashboard(self):
        dashboard = self.env.ref('custom_business_reports.dashboard_commercial')
        data = dashboard.get_dashboard_data({})
        self.assertFalse([(w['title'], w['error']) for w in data['widgets'] if w['error']])
        titles = [w['title'] for w in data['widgets']]
        self.assertEqual(titles[:5], ['Resumen ejecutivo', 'Venta ganada', 'Avance vs meta', 'Meta de venta',
                                      'Pipeline enviado'])
        for name in ('Semana (últimos 7 días)', '% de bateo histórico', 'Trimestre en curso',
                     'Embudo: Totales, Sin Recompra y Recompra', 'Venta por trimestre vs meta acumulada',
                     'Ingenierías'):
            self.assertIn(name, titles)
        self.assertNotIn('Embudo por segmento (periodo seleccionado)', titles)
        venta = next(w for w in data['widgets'] if w['title'] == 'Venta ganada')
        self.assertNotIn('{', venta['subtitle'], 'Las notas ya traen los valores')
        embudo = next(w for w in data['widgets'] if w['title'].startswith('Embudo:'))
        self.assertEqual(embudo['columns'][0]['name'], 'Total')
        # El campo de origen de Studio no existe en la base de pruebas: no se crean esos elementos
        origin = [item for item in COMMERCIAL['widgets'] if item.get('requires')]
        self.assertTrue(origin)
        if not _available(self.env, origin[0]):
            self.assertNotIn('Origen de leads Sin Recompra', titles)

    def test_upgrade_from_v9(self):
        """Simula el tablero de antes de 19.0.10.0.0 y migra."""
        dashboard = self.env.ref('custom_business_reports.dashboard_commercial')
        dashboard.widget_ids.filtered(lambda w: any(
            item['name'] == w.name and item.get('since') == V10 for item in COMMERCIAL['widgets'])).unlink()
        Widget = self.env['business.dashboard.widget']
        model = self.env['ir.model']._get_id('crm.lead')
        Widget.create({'dashboard_id': dashboard.id, 'name': 'Embudo por segmento', 'widget_type': 'section',
                       'sequence': 170})
        Widget.create({'dashboard_id': dashboard.id, 'name': 'Embudo por segmento (periodo seleccionado)',
                       'widget_type': 'table', 'model_id': model, 'sequence': 180,
                       'measure_ids': [(0, 0, {'name': 'N', 'code': 'n', 'aggregate': 'count'})]})
        venta = dashboard.widget_ids.filtered(lambda w: w.name == 'Venta ganada')
        venta.write({'subtitle': OLD_COMMERCIAL_SUBTITLES['Venta ganada'], 'sequence': 10})
        bateo = dashboard.widget_ids.filtered(lambda w: w.name == '% de bateo')
        bateo.write({'subtitle': 'nota del usuario', 'sequence': 70})
        added = _upgrade_commercial_v10(self.env)
        self.assertTrue(len(added) > 40)
        self.assertFalse(_upgrade_commercial_v10(self.env), 'No se duplica')
        self.assertIn('{venta_sr}', venta.subtitle)
        self.assertEqual(bateo.subtitle, 'nota del usuario', 'No pisa la nota del usuario')
        self.assertEqual(bateo.sequence, 34)
        dashboard.invalidate_recordset(['widget_ids'])
        data = dashboard.get_dashboard_data({})
        self.assertFalse([(w['title'], w['error']) for w in data['widgets'] if w['error']])
        self.assertNotIn('Embudo por segmento', [w['title'] for w in data['widgets']])
