# -*- coding: utf-8 -*-
"""Extensión de crm.lead para los reportes comerciales (Etapa 1).

Agrega a cada oportunidad los datos que necesitan los tableros comerciales:

* Segmento (Sin recompra / Recompra / Inadecuado), calculado desde el campo
  Studio "Calidad del lead" con las reglas de crm.lead.segment.rule.
* Grupo de etapa (Prospección, Por enviar, Cotizado, Declinado, Excluido),
  tomado de la configuración de la etapa.
* Fecha de cierre editable y con historial, y registro automático de la
  fecha al entrar a etapas como "Cancelado".
* Último movimiento y días sin movimiento, para dar seguimiento a las
  oportunidades lentas (pueden tardar hasta dos años en cerrarse).
"""
from odoo import api, fields, models
from odoo.tools import SQL

from .const import (
    CLOSE_STATUS_SELECTION,
    IDLE_LATE_DAYS,
    IDLE_WARNING_DAYS,
    INVITATION_STATUS_SELECTION,
    NO_MOVE_FIELDS,
    OPEN_STAGE_GROUPS,
    QUALITY_FIELD,
    SEGMENT_SELECTION,
)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ------------------------------------------------------------------
    # Campos
    # ------------------------------------------------------------------

    # Fecha de cierre estándar de Odoo. Odoo la llena sola al ganar o perder;
    # aquí se vuelve editable (Mauricio corrige el mes real de la venta) y
    # cada cambio queda registrado en el chatter.
    date_closed = fields.Datetime(readonly=False, tracking=True)

    # Segmento comercial. No es un campo "compute" a propósito: depende de un
    # campo Studio y, si ese campo no existiera, un @api.depends impediría
    # instalar el módulo. Se actualiza en create/write y al cambiar reglas.
    report_segment = fields.Selection(
        SEGMENT_SELECTION,
        string='Segmento',
        readonly=True,
        copy=False,
        index=True,
        help='Se calcula desde "Calidad del lead" con las reglas de '
             'CRM › Configuración › Segmentos por calidad del lead.',
    )

    # Grupo de la etapa actual. Guardado en base de datos para poder filtrar
    # y agrupar en listas y tableros.
    report_stage_group = fields.Selection(
        related='stage_id.report_stage_group',
        string='Grupo de etapa',
        store=True,
        index=True,
    )
    # Solo para la vista: indica si la etapa actual registra fecha de cierre.
    report_stage_close_on_enter = fields.Boolean(related='stage_id.report_close_on_enter')

    # Última vez que alguien movió la oportunidad: cualquier cambio de campos,
    # mensaje o nota en el chatter, o actividad programada.
    report_last_move_date = fields.Datetime(
        string='Último movimiento',
        readonly=True,
        copy=False,
        index=True,
        help='Fecha del último cambio, mensaje, nota o actividad registrada.',
    )

    # Días sin movimiento y semáforo. No se guardan porque cambian cada día;
    # para filtrar se usa "Último movimiento".
    report_idle_days = fields.Integer(
        string='Días sin movimiento',
        compute='_compute_report_idle',
    )
    report_idle_level = fields.Selection(
        [('ok', 'Al día'), ('warning', 'Atención'), ('late', 'Sin seguimiento')],
        string='Seguimiento',
        compute='_compute_report_idle',
    )

    # ------------------------------------------------------------------
    # Campos de la Etapa 2 (tablero comercial)
    # ------------------------------------------------------------------

    # Estatus de la etapa para los listados del pipeline (Enviada / En pausa).
    report_open_status = fields.Selection(
        related='stage_id.report_open_status',
        string='Listado del pipeline',
        store=True,
    )

    # Clasificación de la invitación a cotizar: atendida por segmento o no
    # atendida. Alimenta la gráfica apilada "Invitaciones a cotizar".
    report_invitation_status = fields.Selection(
        INVITATION_STATUS_SELECTION,
        string='Invitación a cotizar',
        compute='_compute_report_invitation_status',
        store=True,
        index=True,
    )

    # Resultado de la cotización: ganada o perdida por segmento. Alimenta la
    # gráfica "Ganados y perdidos" y los listados de ganados y perdidos.
    report_close_status = fields.Selection(
        CLOSE_STATUS_SELECTION,
        string='Resultado',
        compute='_compute_report_close_status',
        store=True,
        index=True,
    )

    # Antigüedad (días desde la creación) para los listados de pipeline y
    # pausa. No se guarda porque cambia cada día.
    report_age_days = fields.Integer(
        string='Días desde la creación',
        compute='_compute_report_age_days',
    )

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('report_last_move_date', 'won_status', 'active', 'report_stage_group')
    def _compute_report_idle(self):
        """Días desde el último movimiento, solo para oportunidades abiertas."""
        today = fields.Date.context_today(self)
        for lead in self:
            is_open = (
                lead.active
                and lead.won_status == 'pending'
                and lead.report_stage_group in OPEN_STAGE_GROUPS
                and not lead.report_stage_close_on_enter
            )
            if not is_open or not lead.report_last_move_date:
                lead.report_idle_days = 0
                lead.report_idle_level = False
                continue
            last_day = fields.Date.context_today(lead, lead.report_last_move_date)
            days = max((today - last_day).days, 0)
            lead.report_idle_days = days
            if days >= IDLE_LATE_DAYS:
                lead.report_idle_level = 'late'
            elif days >= IDLE_WARNING_DAYS:
                lead.report_idle_level = 'warning'
            else:
                lead.report_idle_level = 'ok'

    @api.depends('report_stage_group', 'report_segment')
    def _compute_report_invitation_status(self):
        """Invitación atendida (cotizada) por segmento o no atendida (declinada).

        Solo aplica a oportunidades que llegaron a cotizarse o se declinaron;
        las que siguen en prospección o cotizándose quedan vacías.
        """
        for lead in self:
            if lead.report_stage_group == 'declinado':
                lead.report_invitation_status = 'no_atendido'
            elif lead.report_stage_group == 'cotizado':
                lead.report_invitation_status = 'atendido_%s' % (lead.report_segment or 'sin_segmento')
            else:
                lead.report_invitation_status = False

    @api.depends('won_status', 'report_segment', 'report_stage_group')
    def _compute_report_close_status(self):
        """Ganado o perdido por segmento. "Ganados en 0's" no cuenta."""
        segment_key = {'sin_recompra': 'sin_recompra', 'recompra': 'recompra'}
        for lead in self:
            if lead.report_stage_group == 'excluido' or lead.won_status not in ('won', 'lost'):
                lead.report_close_status = False
                continue
            prefix = 'ganado' if lead.won_status == 'won' else 'perdido'
            lead.report_close_status = '%s_%s' % (prefix, segment_key.get(lead.report_segment, 'otro'))

    @api.depends('create_date')
    def _compute_report_age_days(self):
        """Días transcurridos desde que se creó la oportunidad."""
        today = fields.Date.context_today(self)
        for lead in self:
            created = lead.create_date and fields.Date.context_today(lead, lead.create_date)
            lead.report_age_days = (today - created).days if created else 0

    # ------------------------------------------------------------------
    # Altas y cambios
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # Una oportunidad nueva cuenta como movimiento desde su creación.
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault('report_last_move_date', now)
        leads = super().create(vals_list)
        leads._report_update_segment()
        # Por si se crea directamente en una etapa como "Cancelado".
        leads._report_apply_close_on_enter()
        return leads

    def write(self, vals):
        # 1) Registrar el movimiento, salvo que solo cambien campos del sistema
        #    o que la llamada venga de este mismo módulo (contexto ccr_skip_move).
        if (
            not self.env.context.get('ccr_skip_move')
            and set(vals) - NO_MOVE_FIELDS
            and 'report_last_move_date' not in vals
        ):
            vals = dict(vals, report_last_move_date=fields.Datetime.now())

        stage_changed = 'stage_id' in vals
        res = super().write(vals)

        # 2) Si cambió la calidad del lead, recalcular el segmento.
        if QUALITY_FIELD in vals:
            self._report_update_segment()
        # 3) Si cambió la etapa, registrar fecha de cierre en etapas que lo piden.
        #    (Odoo borra la fecha al pasar a una etapa no ganada; aquí se vuelve
        #    a llenar cuando la etapa lo indica.)
        if stage_changed:
            self._report_apply_close_on_enter()
        return res

    # ------------------------------------------------------------------
    # Lógica de apoyo
    # ------------------------------------------------------------------
    def _report_update_segment(self):
        """Calcula el segmento según las reglas y lo guarda si cambió."""
        if QUALITY_FIELD not in self._fields:
            return
        mapping = self.env['crm.lead.segment.rule'].sudo()._get_mapping()
        # Agrupar por segmento destino para escribir en bloque.
        by_segment = {}
        for lead in self:
            target = mapping.get(lead[QUALITY_FIELD]) or False
            if lead.report_segment != target:
                by_segment.setdefault(target, self.browse())
                by_segment[target] |= lead
        for segment, leads in by_segment.items():
            leads.sudo().with_context(ccr_skip_move=True, tracking_disable=True).write(
                {'report_segment': segment}
            )

    def _report_apply_close_on_enter(self):
        """Llena la fecha de cierre al entrar a etapas marcadas (p. ej. Cancelado)."""
        to_close = self.filtered(
            lambda lead: lead.stage_id.report_close_on_enter and not lead.date_closed
        )
        if to_close:
            to_close.with_context(ccr_skip_move=True).write(
                {'date_closed': fields.Datetime.now()}
            )

    def _report_touch(self):
        """Marca "ahora" como último movimiento sin pasar por write().

        Se usa desde el chatter y las actividades. Va por SQL para no alterar
        la fecha de modificación ni generar historial adicional.
        """
        ids = [lead_id for lead_id in self.ids if lead_id]
        if not ids:
            return
        self.env.cr.execute(SQL(
            "UPDATE crm_lead SET report_last_move_date = %s WHERE id IN %s",
            fields.Datetime.now(), tuple(ids),
        ))
        # Invalidar también los días sin movimiento, que dependen de esta fecha.
        self.invalidate_recordset(['report_last_move_date', 'report_idle_days', 'report_idle_level'])

    def _message_post_after_hook(self, message, msg_values):
        """Un mensaje o nota en el chatter cuenta como movimiento.

        Se ignoran las notificaciones internas a usuarios y los mensajes que
        publica el sistema (OdooBot).
        """
        res = super()._message_post_after_hook(message, msg_values)
        odoobot = self.env.ref('base.partner_root', raise_if_not_found=False)
        if message.message_type != 'user_notification' and message.author_id != odoobot:
            self._report_touch()
        return res
