# -*- coding: utf-8 -*-
"""Reporte Semanal de Dirección · Etapa 3 (base de construcción).

Tres modelos:

* business.report.week           Semana de reporte (fecha de corte y estado).
* business.report.week.project   Proyecto en análisis esa semana (una cuenta
                                 analítica) con los datos manuales de NeoData.
* business.report.week.partida   Costo planeado (NeoData) y real (Odoo) de
                                 cada partida del proyecto esa semana.

Flujo:
  Borrador --Iniciar captura--> En captura --Cerrar semana--> Cerrada
  * Iniciar captura copia los proyectos de la semana anterior y arrastra
    venta NeoData, costos planeados y reales anteriores.
  * Mientras está en captura, "Actualizar real" recalcula el real desde Odoo.
  * Al cerrar se guarda la foto del real; una semana cerrada ya no cambia
    aunque se registren movimientos con fecha anterior (solo el gerente
    de proyectos puede reabrirla).
"""
from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from .const import (
    COST_PARTIDA_SELECTION,
    COST_PARTIDAS,
    EXCLUDED_BUDGET_STATES,
    WEEK_STATE_SELECTION,
)


# ======================================================================
# Semana de reporte
# ======================================================================
class BusinessReportWeek(models.Model):
    _name = 'business.report.week'
    _description = 'Semana del Reporte Semanal de Dirección'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='Semana', compute='_compute_name', store=True)
    date = fields.Date(
        string='Fecha de corte', required=True, tracking=True,
        default=fields.Date.context_today,
        help='Los costos reales se toman hasta esta fecha (inclusive).',
    )
    state = fields.Selection(
        WEEK_STATE_SELECTION, string='Estado', default='draft',
        required=True, tracking=True, copy=False,
    )
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related='company_id.currency_id')
    previous_week_id = fields.Many2one(
        'business.report.week', string='Semana anterior',
        compute='_compute_previous_week_id',
    )
    project_line_ids = fields.One2many(
        'business.report.week.project', 'week_id', string='Proyectos en análisis', copy=False,
    )
    real_refresh_date = fields.Datetime(string='Real actualizado el', readonly=True, copy=False)
    note = fields.Html(string='Notas')

    # Resumen de la semana (suma de los proyectos)
    project_count = fields.Integer(string='Proyectos', compute='_compute_totals')
    complete_count = fields.Integer(string='Capturados', compute='_compute_totals')
    planned_total = fields.Monetary(string='Costo planeado', compute='_compute_totals')
    real_total = fields.Monetary(string='Costo real', compute='_compute_totals')
    deviation_total = fields.Monetary(string='Desviación', compute='_compute_totals')
    neodata_advance_total = fields.Monetary(string='Venta semanal NeoData', compute='_compute_totals')

    # Una sola semana por fecha de corte y compañía
    _date_company_uniq = models.Constraint(
        'UNIQUE(company_id, date)',
        'Ya existe una semana de reporte con esa fecha de corte.',
    )

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('date')
    def _compute_name(self):
        for week in self:
            week.name = _('Semana del %s', week.date.strftime('%d/%m/%Y')) if week.date else _('Nueva semana')

    @api.depends('date', 'company_id')
    def _compute_previous_week_id(self):
        """La semana anterior es la de fecha de corte inmediata anterior."""
        for week in self:
            if not week.date:
                week.previous_week_id = False
                continue
            week.previous_week_id = self.search([
                ('company_id', '=', week.company_id.id),
                ('date', '<', week.date),
                ('id', '!=', week._origin.id or 0),
            ], order='date desc', limit=1)

    @api.depends('project_line_ids.capture_state', 'project_line_ids.planned_total',
                 'project_line_ids.real_total', 'project_line_ids.neodata_advance')
    def _compute_totals(self):
        for week in self:
            lines = week.project_line_ids
            week.project_count = len(lines)
            week.complete_count = len(lines.filtered(lambda line: line.capture_state == 'complete'))
            week.planned_total = sum(lines.mapped('planned_total'))
            week.real_total = sum(lines.mapped('real_total'))
            week.deviation_total = week.planned_total - week.real_total
            week.neodata_advance_total = sum(lines.mapped('neodata_advance'))

    # ------------------------------------------------------------------
    # Botones del flujo
    # ------------------------------------------------------------------
    def action_start_capture(self):
        """Borrador -> En captura. Copia los proyectos de la semana anterior."""
        for week in self:
            if week.state != 'draft':
                continue
            if not week.project_line_ids and week.previous_week_id:
                week._copy_projects_from(week.previous_week_id)
            week.state = 'open'
            week.action_refresh_real()
        return True

    def action_refresh_real(self):
        """Recalcula el costo real de todas las partidas hasta la fecha de corte."""
        for week in self:
            if week.state == 'closed':
                raise UserError(_('La semana %s está cerrada: su real ya no se recalcula.', week.name))
            week.project_line_ids._refresh_real_amounts(week.date)
            week.real_refresh_date = fields.Datetime.now()
        return True

    def action_close(self):
        """En captura -> Cerrada. Toma la foto final del real.

        No deja cerrar si hay proyectos sin capturar, para que el histórico
        quede completo.
        """
        for week in self:
            if week.state != 'open':
                raise UserError(_('Solo se puede cerrar una semana en captura.'))
            pending = week.project_line_ids.filtered(lambda line: line.capture_state != 'complete')
            if pending:
                raise UserError(_(
                    'Faltan por capturar estos proyectos:\n%s',
                    '\n'.join('• %s' % name for name in pending.mapped('analytic_account_id.display_name')),
                ))
            week.action_refresh_real()
            week.state = 'closed'
        return True

    def action_reopen(self):
        """Cerrada -> En captura. Solo gerentes de proyectos."""
        if not self.env.user.has_group('project.group_project_manager'):
            raise UserError(_('Solo un gerente de proyectos puede reabrir una semana cerrada.'))
        self.filtered(lambda week: week.state == 'closed').write({'state': 'open'})
        return True

    def _copy_projects_from(self, previous):
        """Crea los proyectos de esta semana a partir de la semana anterior.

        Lo que se arrastra:
        * Venta NeoData de la semana anterior -> "Venta NeoData sem. anterior".
        * Costo planeado anterior -> planeado de esta semana (editable) y
          "planeado sem. anterior".
        * Real anterior -> "real sem. anterior" (para el costo de la semana).
        """
        self.ensure_one()
        vals_list = []
        for prev_line in previous.project_line_ids:
            vals_list.append({
                'week_id': self.id,
                'sequence': prev_line.sequence,
                'analytic_account_id': prev_line.analytic_account_id.id,
                'neodata_sale_prev': prev_line.neodata_sale,
                'oc_review': prev_line.oc_review,
                'estimate_review': prev_line.estimate_review,
                'partida_line_ids': [Command.create({
                    'partida': partida.partida,
                    'planned_amount': partida.planned_amount,
                    'planned_prev': partida.planned_amount,
                    'real_prev': partida.real_amount,
                }) for partida in prev_line.partida_line_ids],
            })
        self.env['business.report.week.project'].with_context(ccr_from_previous=True).create(vals_list)

    def unlink(self):
        if any(week.state != 'draft' for week in self):
            raise UserError(_('Solo se pueden borrar semanas en borrador.'))
        return super().unlink()


# ======================================================================
# Proyecto en análisis de la semana
# ======================================================================
class BusinessReportWeekProject(models.Model):
    _name = 'business.report.week.project'
    _description = 'Proyecto en análisis de la semana'
    _order = 'sequence, id'

    week_id = fields.Many2one('business.report.week', string='Semana', required=True,
                              ondelete='cascade', index=True)
    week_state = fields.Selection(related='week_id.state', string='Estado de la semana')
    week_date = fields.Date(related='week_id.date', string='Fecha de corte', store=True)
    company_id = fields.Many2one(related='week_id.company_id', store=True)
    currency_id = fields.Many2one(related='week_id.currency_id')
    sequence = fields.Integer(default=10)

    # Proyecto = cuenta analítica (así lo maneja DACSA en presupuestos)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Proyecto (cuenta analítica)',
        required=True, index=True,
    )
    project_id = fields.Many2one(
        'project.project', string='Proyecto', compute='_compute_project_id', store=True,
    )

    # ---------------- Datos manuales (NeoData) ----------------
    neodata_sale = fields.Monetary(string='Venta reconocida NeoData')
    neodata_sale_prev = fields.Monetary(
        string='Venta NeoData sem. anterior',
        help='Se llena con la venta NeoData capturada la semana anterior. Editable.',
    )
    oc_review = fields.Monetary(string='OC en revisión')
    estimate_review = fields.Monetary(string='Estimación en revisión')
    note = fields.Char(string='Comentario')

    # ---------------- Partidas ----------------
    partida_line_ids = fields.One2many(
        'business.report.week.partida', 'project_line_id', string='Partidas',
    )

    # ---------------- Cálculos ----------------
    neodata_advance = fields.Monetary(
        string='Avance semanal NeoData', compute='_compute_amounts', store=True,
        help='Venta NeoData actual − venta NeoData de la semana anterior.',
    )
    planned_total = fields.Monetary(string='Costo planeado', compute='_compute_amounts', store=True)
    planned_prev_total = fields.Monetary(string='Planeado sem. anterior', compute='_compute_amounts', store=True)
    real_total = fields.Monetary(string='Costo real', compute='_compute_amounts', store=True)
    real_prev_total = fields.Monetary(string='Real sem. anterior', compute='_compute_amounts', store=True)
    deviation = fields.Monetary(
        string='Desviación', compute='_compute_amounts', store=True,
        help='Costo planeado − costo real. Positivo = optimización.',
    )
    week_cost = fields.Monetary(
        string='Costo de la semana', compute='_compute_amounts', store=True,
        help='Costo real hoy − costo real de la semana anterior.',
    )
    week_difference = fields.Monetary(
        string='Diferencia semanal', compute='_compute_amounts', store=True,
        help='Avance semanal NeoData − costo de la semana.',
    )
    neodata_margin = fields.Monetary(
        string='Margen NeoData', compute='_compute_amounts', store=True,
        help='Venta reconocida NeoData − costo real.',
    )
    neodata_margin_pct = fields.Float(string='% Margen NeoData', compute='_compute_amounts', store=True)
    capture_state = fields.Selection(
        [('pending', 'Pendiente'), ('complete', 'Completo')],
        string='Captura', compute='_compute_amounts', store=True,
    )

    _week_account_uniq = models.Constraint(
        'UNIQUE(week_id, analytic_account_id)',
        'El proyecto ya está en esta semana.',
    )

    @api.depends('analytic_account_id')
    def _compute_project_id(self):
        Project = self.env['project.project'].sudo()
        for line in self:
            line.project_id = Project.search([('account_id', '=', line.analytic_account_id.id)], limit=1) \
                if line.analytic_account_id else False

    @api.depends('neodata_sale', 'neodata_sale_prev',
                 'partida_line_ids.planned_amount', 'partida_line_ids.planned_prev',
                 'partida_line_ids.real_amount', 'partida_line_ids.real_prev')
    def _compute_amounts(self):
        for line in self:
            partidas = line.partida_line_ids
            line.planned_total = sum(partidas.mapped('planned_amount'))
            line.planned_prev_total = sum(partidas.mapped('planned_prev'))
            line.real_total = sum(partidas.mapped('real_amount'))
            line.real_prev_total = sum(partidas.mapped('real_prev'))
            line.deviation = line.planned_total - line.real_total
            # Mientras no se capture la venta NeoData de la semana, el avance
            # y el margen quedan en cero (evita avances negativos falsos).
            line.neodata_advance = line.neodata_sale - line.neodata_sale_prev if line.neodata_sale else 0.0
            line.week_cost = line.real_total - line.real_prev_total
            line.week_difference = line.neodata_advance - line.week_cost
            line.neodata_margin = line.neodata_sale - line.real_total if line.neodata_sale else 0.0
            line.neodata_margin_pct = line.neodata_margin / line.neodata_sale if line.neodata_sale else 0.0
            # Completo: venta NeoData y costo planeado capturados
            line.capture_state = 'complete' if line.neodata_sale and line.planned_total else 'pending'

    # ------------------------------------------------------------------
    # Altas y protección de semanas cerradas
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('ccr_from_previous'):
            lines._fill_from_previous_week()
        lines._ensure_partidas()
        return lines

    def write(self, vals):
        self._check_week_not_closed()
        return super().write(vals)

    def unlink(self):
        self._check_week_not_closed()
        return super().unlink()

    def _check_week_not_closed(self):
        if self.env.context.get('ccr_allow_closed'):
            return
        if any(line.week_id.state == 'closed' for line in self):
            raise UserError(_('La semana está cerrada. Para corregir algo hay que reabrirla.'))

    def _fill_from_previous_week(self):
        """Proyecto agregado a mano: toma lo que tenía en la semana anterior."""
        for line in self:
            previous = line.week_id.previous_week_id
            prev_line = previous.project_line_ids.filtered(
                lambda p: p.analytic_account_id == line.analytic_account_id) if previous else False
            if not prev_line:
                continue
            line.neodata_sale_prev = prev_line.neodata_sale
            line.partida_line_ids = [Command.create({
                'partida': partida.partida,
                'planned_amount': partida.planned_amount,
                'planned_prev': partida.planned_amount,
                'real_prev': partida.real_amount,
            }) for partida in prev_line.partida_line_ids]

    def _ensure_partidas(self):
        """Cada proyecto lleva siempre las 5 partidas de costo."""
        for line in self:
            existing = set(line.partida_line_ids.mapped('partida'))
            missing = [p for p in COST_PARTIDAS if p not in existing]
            if missing:
                line.partida_line_ids = [Command.create({'partida': p}) for p in missing]

    # ------------------------------------------------------------------
    # Costo real desde Odoo
    # ------------------------------------------------------------------
    def _get_real_by_partida(self, cutoff):
        """Costo real por partida de cada proyecto hasta la fecha de corte.

        Usa la misma lógica que el "Real" del presupuesto por posición
        (custom_budget_project): por cada línea de presupuesto del proyecto,
        suma los apuntes analíticos de su cuenta analítica y de las cuentas
        contables de su posición, dentro del periodo de la línea, pero solo
        hasta la fecha de corte. Los costos vienen en negativo en contabilidad;
        aquí se devuelven en positivo.

        Regresa {id del proyecto en análisis: {partida: importe}}.
        """
        result = defaultdict(lambda: defaultdict(float))
        BudgetLine = self.env['budget.lines'].sudo()
        AnalyticLine = self.env['account.analytic.line'].sudo()
        for line in self:
            account = line.analytic_account_id
            budget_lines = BudgetLine.search([
                ('analytic_account_id', '=', account.id),
                ('budget_id.state', 'not in', EXCLUDED_BUDGET_STATES),
                ('general_budget_id.report_partida', 'in', COST_PARTIDAS),
            ])
            column = account.plan_id._column_name()
            for budget_line in budget_lines:
                date_to = min(budget_line.date_to, cutoff) if budget_line.date_to else cutoff
                if budget_line.date_from and budget_line.date_from > date_to:
                    continue
                domain = [(column, '=', account.id), ('date', '<=', date_to)]
                if budget_line.date_from:
                    domain.append(('date', '>=', budget_line.date_from))
                general_accounts = budget_line.general_budget_id.account_ids
                if general_accounts:
                    domain.append(('general_account_id', 'in', general_accounts.ids))
                [(amount,)] = AnalyticLine._read_group(domain, [], ['amount:sum'])
                result[line.id][budget_line.general_budget_id.report_partida] += -(amount or 0.0)
        return result

    def _refresh_real_amounts(self, cutoff):
        """Escribe el real de cada partida (la "foto" de la semana)."""
        reals = self._get_real_by_partida(cutoff)
        for line in self:
            for partida in line.partida_line_ids:
                amount = reals[line.id].get(partida.partida, 0.0)
                if partida.real_amount != amount:
                    partida.with_context(ccr_allow_closed=True).real_amount = amount

    # ------------------------------------------------------------------
    # Botones
    # ------------------------------------------------------------------
    def action_open_capture(self):
        """Abre el detalle del proyecto para capturar sus partidas."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('custom_business_reports.business_report_week_project_view_form').id, 'form')],
            'target': 'new',
            'name': self.analytic_account_id.display_name,
        }


# ======================================================================
# Partida (costo planeado y real) del proyecto en la semana
# ======================================================================
class BusinessReportWeekPartida(models.Model):
    _name = 'business.report.week.partida'
    _description = 'Partida de costo del proyecto en la semana'
    _order = 'project_line_id, sequence'

    project_line_id = fields.Many2one('business.report.week.project', string='Proyecto',
                                      required=True, ondelete='cascade', index=True)
    week_id = fields.Many2one(related='project_line_id.week_id', store=True)
    week_date = fields.Date(related='project_line_id.week_date', store=True)
    analytic_account_id = fields.Many2one(related='project_line_id.analytic_account_id', store=True)
    currency_id = fields.Many2one(related='project_line_id.currency_id')
    partida = fields.Selection(COST_PARTIDA_SELECTION, string='Partida', required=True)
    sequence = fields.Integer(compute='_compute_sequence', store=True)

    planned_amount = fields.Monetary(string='Planeado NeoData')
    planned_prev = fields.Monetary(string='Planeado sem. anterior')
    real_amount = fields.Monetary(string='Real Odoo', readonly=True,
                                  help='Costo real hasta la fecha de corte. Se congela al cerrar la semana.')
    real_prev = fields.Monetary(string='Real sem. anterior')

    planned_delta = fields.Monetary(string='Δ Planeado', compute='_compute_deltas', store=True)
    real_delta = fields.Monetary(string='Δ Real', compute='_compute_deltas', store=True)
    deviation = fields.Monetary(string='Desviación', compute='_compute_deltas', store=True,
                                help='Planeado − real. Positivo = optimización.')
    deviation_pct = fields.Float(string='% Desviación', compute='_compute_deltas', store=True)
    week_difference = fields.Monetary(string='Diferencia semanal', compute='_compute_deltas', store=True,
                                      help='Δ planeado − Δ real de la semana.')

    _project_partida_uniq = models.Constraint(
        'UNIQUE(project_line_id, partida)',
        'La partida ya existe en este proyecto.',
    )

    @api.depends('partida')
    def _compute_sequence(self):
        for partida in self:
            partida.sequence = COST_PARTIDAS.index(partida.partida) if partida.partida in COST_PARTIDAS else 99

    @api.depends('planned_amount', 'planned_prev', 'real_amount', 'real_prev')
    def _compute_deltas(self):
        for partida in self:
            partida.planned_delta = partida.planned_amount - partida.planned_prev
            partida.real_delta = partida.real_amount - partida.real_prev
            partida.deviation = partida.planned_amount - partida.real_amount
            partida.deviation_pct = partida.deviation / partida.planned_amount if partida.planned_amount else 0.0
            partida.week_difference = partida.planned_delta - partida.real_delta

    def write(self, vals):
        if not self.env.context.get('ccr_allow_closed') and any(
                p.project_line_id.week_id.state == 'closed' for p in self):
            raise UserError(_('La semana está cerrada. Para corregir algo hay que reabrirla.'))
        return super().write(vals)

    def action_open_entries(self):
        """Apuntes analíticos que forman el real de esta partida."""
        self.ensure_one()
        line = self.project_line_id
        account = line.analytic_account_id
        posts = self.env['budget.lines'].sudo().search([
            ('analytic_account_id', '=', account.id),
            ('budget_id.state', 'not in', EXCLUDED_BUDGET_STATES),
            ('general_budget_id.report_partida', '=', self.partida),
        ]).mapped('general_budget_id')
        domain = [
            (account.plan_id._column_name(), '=', account.id),
            ('date', '<=', line.week_date),
        ]
        if posts.account_ids:
            domain.append(('general_account_id', 'in', posts.account_ids.ids))
        return {
            'type': 'ir.actions.act_window',
            'name': _('%(partida)s · %(project)s', partida=dict(COST_PARTIDA_SELECTION)[self.partida],
                      project=account.display_name),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,pivot',
            'domain': domain,
            'context': {'create': False},
        }
