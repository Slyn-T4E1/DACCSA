# -*- coding: utf-8 -*-
"""Programar una actividad sobre una oportunidad cuenta como movimiento.

(Marcar una actividad como hecha publica un mensaje en el chatter, que ya se
registra en crm.lead._message_post_after_hook.)
"""
from odoo import api, models


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model_create_multi
    def create(self, vals_list):
        activities = super().create(vals_list)
        lead_ids = activities.filtered(lambda act: act.res_model == 'crm.lead').mapped('res_id')
        if lead_ids:
            self.env['crm.lead'].browse(lead_ids).exists()._report_touch()
        return activities
