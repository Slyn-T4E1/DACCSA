# -*- coding: utf-8 -*-
"""PDF del Reporte Semanal de Dirección (Etapa 7).

* business.report.week.print   Asistente: qué secciones y qué proyectos llevar.
* report.custom_business_reports.report_week_direction
                               Arma los datos del PDF (mismo cálculo que el
                               tablero y la semana) y las gráficas en SVG.

Orden del PDF (como el PowerPoint de Dirección):
  Resumen: portada, indicadores y proyectos, balance de costos por partida,
           indicadores de costos y venta, margen operativo al momento.
  Por proyecto: portada, balance financiero, costos, semana (costos 2).
Solo las semanas cerradas guardan el PDF en la semana (queda en el historial);
las semanas en captura generan una vista previa con marca de agua.
"""
import base64
from collections import OrderedDict

from babel.dates import format_date as babel_format_date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import report_charts as charts
from .const import COST_PARTIDA_SELECTION, COST_PARTIDAS

REPORT_XMLID = 'custom_business_reports.action_report_week_direction'
FOOTER = 'Propiedad de DACCSA – Uso Restringido · CON-FO-17 Rev.00'
HISTORY_WEEKS = 6       # semanas que se muestran en tendencias


# ======================================================================
# Asistente
# ======================================================================
class BusinessReportWeekPrint(models.TransientModel):
    _name = 'business.report.week.print'
    _description = 'Generar Reporte Semanal de Dirección (PDF)'

    week_id = fields.Many2one('business.report.week', string='Semana', required=True, readonly=True)
    week_state = fields.Selection(related='week_id.state')
    include_summary = fields.Boolean(string='Resumen de Dirección', default=True,
                                     help='Portada, indicadores, balance por partida, tendencia y márgenes.')
    include_projects = fields.Boolean(string='Una sección por proyecto', default=True,
                                      help='Portada, balance financiero, costos y semana de cada proyecto.')
    project_line_ids = fields.Many2many(
        'business.report.week.project', string='Proyectos',
        domain="[('week_id', '=', week_id)]",
        help='Proyectos que lleva el PDF. Vacío = todos los de la semana.')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        week_id = values.get('week_id') or self.env.context.get('active_id')
        if week_id and self.env.context.get('active_model', 'business.report.week') == 'business.report.week':
            values['week_id'] = week_id
            values['project_line_ids'] = [(6, 0, self.env['business.report.week'].browse(week_id).project_line_ids.ids)]
        return values

    def _report_data(self):
        return {
            'line_ids': self.project_line_ids.ids,
            'include_summary': self.include_summary,
            'include_projects': self.include_projects,
        }

    def action_print(self):
        """Semana cerrada: guarda el PDF en la semana y lo descarga.
        Semana en captura: descarga una vista previa (no se guarda)."""
        self.ensure_one()
        if not self.include_summary and not self.include_projects:
            raise UserError(_('Elige al menos una sección.'))
        week = self.week_id
        if week.state != 'closed':
            return self.env.ref(REPORT_XMLID).report_action(week, data=self._report_data(), config=False)
        attachment = week._save_direction_report(self._report_data())
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }


# ======================================================================
# Semana: guardar y enviar el PDF
# ======================================================================
class BusinessReportWeek(models.Model):
    _inherit = 'business.report.week'

    report_attachment_id = fields.Many2one('ir.attachment', string='Último PDF', readonly=True, copy=False)

    def action_open_print_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reporte Semanal de Dirección'),
            'res_model': 'business.report.week.print',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_week_id': self.id, 'active_id': self.id, 'active_model': self._name},
        }

    def _direction_report_filename(self):
        self.ensure_one()
        return 'Reporte semanal Direccion %s.pdf' % self.date.strftime('%Y-%m-%d')

    def _save_direction_report(self, data=None):
        """Genera el PDF, lo adjunta a la semana y lo deja en el historial."""
        self.ensure_one()
        pdf, _report_type = self.env['ir.actions.report']._render_qweb_pdf(REPORT_XMLID, self.ids, data=data)
        attachment = self.env['ir.attachment'].create({
            'name': self._direction_report_filename(),
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        self.report_attachment_id = attachment
        self.message_post(body=_('Se generó el Reporte Semanal de Dirección.'), attachment_ids=attachment.ids)
        return attachment

    def action_send_direction_report(self):
        """Abre el correo con el PDF de la semana (la plantilla lo adjunta)."""
        self.ensure_one()
        if self.state != 'closed':
            raise UserError(_('Solo se envía el reporte de semanas cerradas.'))
        template = self.env.ref('custom_business_reports.mail_template_week_direction', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': self._name,
                'default_res_ids': self.ids,
                'default_template_id': template.id if template else False,
                'default_composition_mode': 'comment',
            },
        }


class BusinessReportWeekProject(models.Model):
    _inherit = 'business.report.week.project'

    def _report_client(self):
        """Cliente del proyecto: el de la cuenta analítica o, si no tiene, el del proyecto."""
        self.ensure_one()
        partner = self.analytic_account_id.partner_id or self.project_id.partner_id
        return partner.commercial_partner_id


# ======================================================================
# Datos del PDF
# ======================================================================
class ReportWeekDirection(models.AbstractModel):
    _name = 'report.custom_business_reports.report_week_direction'
    _description = 'Reporte Semanal de Dirección (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        weeks = self.env['business.report.week'].browse(docids)
        reports = [self._week_values(week, data) for week in weeks]
        return {
            'doc_ids': docids,
            'doc_model': 'business.report.week',
            'docs': weeks,
            'reports': reports,
            'money': charts.money,
            'short': charts.short,
            'pct': charts.pct,
            'footer': FOOTER,
        }

    # ------------------------------------------------------------------
    def _week_values(self, week, data):
        lines = week.project_line_ids
        if data.get('line_ids'):
            lines = lines.filtered(lambda line: line.id in data['line_ids'])
        lang = self.env.user.lang or 'es_MX'
        long_date = babel_format_date(week.date, format="d 'de' MMMM 'de' y", locale=lang).capitalize() \
            if week.date else ''
        labels = dict(COST_PARTIDA_SELECTION)
        partidas = self._partida_totals(lines)
        estimate = sum(lines.mapped('estimate_amount'))
        real = sum(lines.mapped('real_total'))
        planned = sum(partidas[p]['planned'] for p in COST_PARTIDAS)
        real_partidas = sum(partidas[p]['real'] for p in COST_PARTIDAS)
        margin = estimate - real
        values = {
            'week': week,
            'company': week.company_id,
            'long_date': long_date,
            'preview': week.state != 'closed',
            'include_summary': data.get('include_summary', True),
            'include_projects': data.get('include_projects', True),
            'lines': lines,
            'clients': self._clients(lines),
            'kpis': {
                'planned': planned, 'real': real_partidas, 'deviation': planned - real_partidas,
                'deviation_pct': (planned - real_partidas) / planned if planned else 0.0,
                'deviation_delta': sum(partidas[p]['planned_delta'] - partidas[p]['real_delta'] for p in COST_PARTIDAS),
                'planned_delta': sum(partidas[p]['planned_delta'] for p in COST_PARTIDAS),
                'real_delta': sum(partidas[p]['real_delta'] for p in COST_PARTIDAS),
                'sale_week': sum(lines.mapped('neodata_advance')),
                'estimate': estimate, 'cost': real, 'margin': margin,
                'margin_pct': margin / estimate if estimate else 0.0,
                'alert': week.margin_alert_pct,
            },
            'partidas': [dict(partidas[p], key=p, label=labels[p]) for p in COST_PARTIDAS],
            'partida_chart': charts.bar_chart(
                [labels[p] for p in COST_PARTIDAS],
                [('Planeado (NeoData)', '#2F5BEA', [partidas[p]['planned'] for p in COST_PARTIDAS]),
                 ('Real (Odoo)', '#E8556F', [partidas[p]['real'] for p in COST_PARTIDAS])],
                height=240),
            'projects': [self._project_values(line, labels) for line in lines],
        }
        values['trend'] = self._trend(week, lines)
        return values

    def _partida_totals(self, lines):
        totals = OrderedDict((p, {'planned': 0.0, 'real': 0.0, 'planned_delta': 0.0, 'real_delta': 0.0})
                             for p in COST_PARTIDAS)
        for partida in lines.mapped('partida_line_ids'):
            if partida.partida in totals:
                item = totals[partida.partida]
                item['planned'] += partida.planned_amount
                item['real'] += partida.real_amount
                item['planned_delta'] += partida.planned_delta
                item['real_delta'] += partida.real_delta
        for item in totals.values():
            item['deviation'] = item['planned'] - item['real']
            item['deviation_pct'] = item['deviation'] / item['planned'] if item['planned'] else 0.0
        return totals

    def _clients(self, lines):
        """Proyectos agrupados por cliente (contacto de la cuenta analítica)."""
        clients = OrderedDict()
        for line in lines:
            partner = line._report_client()
            clients.setdefault(partner.display_name or _('Sin cliente'), []).append(line)
        return list(clients.items())

    def _trend(self, week, lines):
        """Balance de costos y venta semanal de las últimas semanas (mismos proyectos)."""
        accounts = lines.mapped('analytic_account_id')
        history = self.env['business.report.week.project'].search([
            ('company_id', '=', week.company_id.id),
            ('week_date', '<=', week.date),
            ('analytic_account_id', 'in', accounts.ids),
        ])
        by_week = OrderedDict()
        for line in history.sorted('week_date'):
            item = by_week.setdefault(line.week_date, {'balance': 0.0, 'sale': 0.0})
            item['balance'] += line.deviation
            item['sale'] += line.neodata_advance
        dates = list(by_week)[-HISTORY_WEEKS:]
        labels = [d.strftime('%d/%m') for d in dates]
        rows = [{'label': d.strftime('%d/%m/%Y'), **by_week[d]} for d in dates]
        chart = charts.line_chart(labels, [
            ('Balance de costos (planeado − real)', '#2F5BEA', [by_week[d]['balance'] for d in dates]),
            ('Venta semanal (avance NeoData)', '#F59E0B', [by_week[d]['sale'] for d in dates]),
        ], height=280)
        return {'rows': rows, 'chart': chart}

    def _project_values(self, line, labels):
        partidas = line.partida_line_ids.sorted('sequence')
        history = line.history_line_ids.sorted('week_date')[-HISTORY_WEEKS:]
        finance_items = [
            ('Valor contrato', line.contract_amount, '#15803D'),
            ('OC en revisión', line.oc_review, '#9CA3AF'),
            ('Venta NeoData sem. actual', line.neodata_sale, '#E07A1F'),
            ('Estimado autorizado', line.estimate_amount, '#2F5BEA'),
            ('Restante por estimar', line.remaining_estimate, '#EAB308'),
            ('Estimación en revisión', line.estimate_review, '#9CA3AF'),
            ('Facturado', line.invoiced_amount, '#A8A29E'),
        ]
        return {
            'line': line,
            'client': line._report_client().display_name or '',
            'finance_chart': charts.hbar_list(finance_items, width=600),
            'margin_chart': charts.bar_chart(
                [h.week_date.strftime('%d/%m') for h in history],
                [('Margen NeoData', '#93C5FD', [h.neodata_margin for h in history])],
                width=560, height=250),
            'cost_chart': charts.bar_chart(
                [labels.get(p.partida, '') for p in partidas],
                [('Planeado (NeoData)', '#2F5BEA', partidas.mapped('planned_amount')),
                 ('Real (Odoo)', '#E8556F', partidas.mapped('real_amount'))],
                width=700, height=240),
            'delta_chart': charts.bar_chart(
                [labels.get(p.partida, '') for p in partidas],
                [('Δ planeado', '#2F5BEA', partidas.mapped('planned_delta')),
                 ('Δ real', '#93C5FD', partidas.mapped('real_delta')),
                 ('Diferencia', '#10B981', partidas.mapped('week_difference'))],
                width=1180, height=210),
            'partidas': partidas,
            'labels': labels,
            'history': history,
        }
