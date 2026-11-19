# -*- coding: utf-8 -*-
"""Pruebas de la Etapa 1 (CRM).

Ejecutar en Odoo.sh / local con:
    odoo-bin -d <base> -u custom_business_reports --test-tags /custom_business_reports
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import SQL

from odoo.addons.custom_business_reports.models.const import QUALITY_FIELD


@tagged('post_install', '-at_install')
class TestCrmReports(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Stage = cls.env['crm.stage']
        # Etapas de prueba con su configuración de reporte
        cls.stage_sent = Stage.create({'name': 'CCR Enviada', 'report_stage_group': 'cotizado'})
        cls.stage_cancel = Stage.create({
            'name': 'CCR Cancelado', 'report_stage_group': 'cotizado', 'report_close_on_enter': True,
        })
        cls.stage_zero = Stage.create({'name': "CCR Ganados en 0's", 'report_stage_group': 'excluido'})
        cls.lead = cls.env['crm.lead'].create({
            'name': 'CCR oportunidad de prueba',
            'type': 'opportunity',
            'stage_id': cls.stage_sent.id,
        })

    def _set_last_move(self, lead, days_ago):
        """Fuerza el último movimiento a hace N días (sin pasar por write)."""
        value = fields.Datetime.now() - timedelta(days=days_ago)
        self.env.cr.execute(SQL(
            "UPDATE crm_lead SET report_last_move_date = %s WHERE id = %s", value, lead.id))
        # Invalidar todo el registro: los días sin movimiento se recalculan
        lead.invalidate_recordset()
        return value

    def test_stage_group_is_stored_on_lead(self):
        """El grupo de etapa se copia a la oportunidad y cambia con la etapa."""
        self.assertEqual(self.lead.report_stage_group, 'cotizado')
        self.lead.stage_id = self.stage_zero
        self.assertEqual(self.lead.report_stage_group, 'excluido')

    def test_close_date_on_cancel_stage(self):
        """Entrar a una etapa con "registrar fecha de cierre" llena la fecha."""
        self.assertFalse(self.lead.date_closed)
        self.lead.stage_id = self.stage_cancel
        self.assertTrue(self.lead.date_closed)
        # Al regresar a una etapa abierta, Odoo vuelve a borrar la fecha.
        self.lead.stage_id = self.stage_sent
        self.assertFalse(self.lead.date_closed)

    def test_close_date_is_editable(self):
        """La fecha de cierre de una oportunidad ganada se puede corregir."""
        self.lead.action_set_won()
        new_date = fields.Datetime.to_datetime('2026-04-29 12:00:00')
        self.lead.date_closed = new_date
        self.assertEqual(self.lead.date_closed, new_date)

    def test_last_move_on_write_and_message(self):
        """Cambios y notas actualizan el último movimiento; los del sistema no."""
        old = self._set_last_move(self.lead, 200)
        # Campo del sistema: no cuenta
        self.lead.write({'automated_probability': 33})
        self.assertEqual(self.lead.report_last_move_date, old)
        # Nota en el chatter: sí cuenta
        # (como usuario real: los mensajes de OdooBot no cuentan como movimiento)
        user = self.env.ref('base.user_admin')
        self.lead.with_user(user).message_post(body='Seguimiento', message_type='comment', subtype_xmlid='mail.mt_note')
        self.lead.invalidate_recordset()
        self.assertGreater(self.lead.report_last_move_date, old)
        # Cambio de un campo: sí cuenta
        old = self._set_last_move(self.lead, 200)
        self.lead.write({'name': 'CCR oportunidad renombrada'})
        self.assertGreater(self.lead.report_last_move_date, old)

    def test_idle_level(self):
        """Semáforo: más de 90 días sin movimiento = rojo; recién movida = verde."""
        self._set_last_move(self.lead, 120)
        self.assertEqual(self.lead.report_idle_level, 'late')
        self.assertGreaterEqual(self.lead.report_idle_days, 119)
        self._set_last_move(self.lead, 40)
        self.assertEqual(self.lead.report_idle_level, 'warning')
        self._set_last_move(self.lead, 0)
        self.assertEqual(self.lead.report_idle_level, 'ok')
        # Una oportunidad ganada ya no se mide
        self.lead.action_set_won()
        self.assertFalse(self.lead.report_idle_level)

    def test_segment_from_quality(self):
        """El segmento se calcula desde la Calidad del lead según las reglas."""
        if QUALITY_FIELD not in self.env['crm.lead']._fields:
            self.skipTest('La base no tiene el campo Studio %s' % QUALITY_FIELD)
        Rule = self.env['crm.lead.segment.rule']
        options = Rule._selection_quality_value()
        self.assertTrue(options, 'El campo de calidad no tiene opciones')
        value = options[0][0]
        rule = Rule.search([('quality_value', '=', value)])
        if not rule:
            rule = Rule.create({'quality_value': value, 'segment': 'sin_recompra'})
        self.lead.write({QUALITY_FIELD: value})
        self.assertEqual(self.lead.report_segment, rule.segment)
        # Cambiar la regla recalcula las oportunidades existentes
        other = 'recompra' if rule.segment != 'recompra' else 'inadecuado'
        rule.segment = other
        self.lead.invalidate_recordset(['report_segment'])
        self.assertEqual(self.lead.report_segment, other)


@tagged('post_install', '-at_install')
class TestCommercialDashboard(TransactionCase):
    """Pruebas de la Etapa 2 (seguimiento comercial)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Stage = cls.env['crm.stage']
        cls.stage_sent = Stage.create({
            'name': 'CCR2 Enviada', 'report_stage_group': 'cotizado', 'report_open_status': 'enviada',
        })
        cls.stage_declined = Stage.create({'name': 'CCR2 No se participó', 'report_stage_group': 'declinado'})
        cls.stage_zero = Stage.create({'name': "CCR2 Ganados en 0's", 'report_stage_group': 'excluido'})
        cls.stage_idea = Stage.create({'name': 'CCR2 Idea', 'report_stage_group': 'prospeccion'})
        cls.lead = cls.env['crm.lead'].create({
            'name': 'CCR2 oportunidad', 'type': 'opportunity', 'stage_id': cls.stage_sent.id,
        })

    def _set_segment(self, segment):
        """Fija el segmento directamente (sin depender del campo Studio)."""
        self.lead.with_context(ccr_skip_move=True).write({'report_segment': segment})

    def test_invitation_status(self):
        """Cotizada = atendida por segmento; declinada = no atendida; prospección = vacío."""
        self._set_segment('recompra')
        self.assertEqual(self.lead.report_invitation_status, 'atendido_recompra')
        self.assertEqual(self.lead.report_open_status, 'enviada')
        self.lead.stage_id = self.stage_declined
        self.assertEqual(self.lead.report_invitation_status, 'no_atendido')
        self.lead.stage_id = self.stage_idea
        self.assertFalse(self.lead.report_invitation_status)

    def test_close_status(self):
        """Ganado / perdido por segmento; Ganados en 0's no cuenta."""
        self._set_segment('sin_recompra')
        self.assertFalse(self.lead.report_close_status)
        self.lead.action_set_lost()
        self.assertEqual(self.lead.report_close_status, 'perdido_sin_recompra')
        self.lead.action_unarchive()
        self.lead.action_set_won()
        self.assertEqual(self.lead.report_close_status, 'ganado_sin_recompra')
        self.lead.stage_id = self.stage_zero
        self.assertFalse(self.lead.report_close_status)

    def test_report_actions_run(self):
        """Las acciones del menú Seguimiento comercial abren sin error."""
        from odoo.tools.safe_eval import safe_eval
        xmlids = self.env['ir.model.data'].search([
            ('module', '=', 'custom_business_reports'),
            ('model', '=', 'ir.actions.act_window'),
        ])
        actions = self.env['ir.actions.act_window'].browse(xmlids.mapped('res_id'))
        self.assertGreaterEqual(len(actions), 11)
        for action in actions:
            domain = safe_eval(action.domain or '[]')
            ctx = safe_eval(action.context or '{}')
            self.env['crm.lead'].with_context(active_test=ctx.get('active_test', True)).search(domain, limit=1)
