# -*- coding: utf-8 -*-
"""Reglas para convertir la "Calidad del lead" (Studio) en un Segmento.

Ejemplo de DACSA:
    1. Idóneo     -> Sin recompra
    2. Bueno      -> Sin recompra
    3. Inadecuado -> Inadecuado
    4. Recompra   -> Recompra

Las reglas se editan en CRM › Configuración › Segmentos por calidad del lead,
sin programar. Al crear, cambiar o borrar una regla se recalcula el segmento
de todas las oportunidades.
"""
from odoo import api, fields, models

from .const import QUALITY_FIELD, SEGMENT_SELECTION


class CrmLeadSegmentRule(models.Model):
    _name = 'crm.lead.segment.rule'
    _description = 'Regla de segmento por calidad del lead'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)

    # Valor del campo Studio. Las opciones se leen del propio campo para que
    # siempre coincidan con lo que el usuario ve en la oportunidad.
    quality_value = fields.Selection(
        selection='_selection_quality_value',
        string='Calidad del lead',
        required=True,
    )
    segment = fields.Selection(SEGMENT_SELECTION, string='Segmento', required=True)

    # Una calidad solo puede pertenecer a un segmento.
    _quality_value_uniq = models.Constraint(
        'UNIQUE(quality_value)',
        'Cada calidad del lead solo puede tener una regla.',
    )

    @api.model
    def _selection_quality_value(self):
        """Opciones del campo Studio "Calidad del lead" (vacío si no existe)."""
        field = self.env['crm.lead']._fields.get(QUALITY_FIELD)
        if not field or field.type != 'selection':
            return []
        return field._description_selection(self.env)

    @api.model
    def _get_mapping(self):
        """Diccionario {valor de calidad: segmento} con las reglas vigentes."""
        return {rule.quality_value: rule.segment for rule in self.search([])}

    # ------------------------------------------------------------------
    # Recalcular segmentos cuando cambian las reglas
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        self._recompute_all_leads()
        return rules

    def write(self, vals):
        res = super().write(vals)
        self._recompute_all_leads()
        return res

    def unlink(self):
        res = super().unlink()
        self._recompute_all_leads()
        return res

    @api.model
    def _recompute_all_leads(self):
        """Recalcula el segmento de todas las oportunidades (activas y perdidas)."""
        leads = self.env['crm.lead'].sudo().with_context(active_test=False).search([])
        leads._report_update_segment()

    def action_recompute_segments(self):
        """Botón "Recalcular segmentos" de la lista de reglas."""
        self._recompute_all_leads()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': 'Se recalculó el segmento de todas las oportunidades.',
                'sticky': False,
            },
        }
