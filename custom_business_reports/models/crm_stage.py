# -*- coding: utf-8 -*-
"""Configuración de reportes en las etapas del CRM (crm.stage)."""
from odoo import fields, models

from .const import STAGE_GROUP_SELECTION


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    # Grupo de la etapa para los tableros. Se configura una sola vez por etapa
    # (Configuración › Etapas) y todas las oportunidades lo heredan.
    report_stage_group = fields.Selection(
        STAGE_GROUP_SELECTION,
        string='Grupo para reportes',
        help='Agrupa la etapa en los reportes comerciales: Prospección, Por '
             'enviar, Cotizado, Declinado o Excluido de tableros.',
    )

    # Odoo solo registra la fecha de cierre al ganar o perder. Con esta casilla
    # también se registra al entrar a etapas de cierre propias de DACSA,
    # como "Cancelado".
    report_close_on_enter = fields.Boolean(
        string='Registrar fecha de cierre al entrar',
        help='Al mover una oportunidad a esta etapa se llena la fecha de '
             'cierre (si estaba vacía). Pensado para "Cancelado".',
    )
