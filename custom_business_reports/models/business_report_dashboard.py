# -*- coding: utf-8 -*-
"""Reporte Semanal de Dirección · Etapa 5 (Tablero de Dirección).

Vistas SQL de solo lectura que resumen todas las semanas para las tablas y
gráficas del tablero. No guardan datos: siempre leen lo que hay en las
semanas, proyectos y partidas.

* business.report.week.partida.summary  Balance de costos por partida de cada
                                         semana (suma de todos los proyectos).
* business.report.dashboard.cost        Planeado y real por partida en renglones
                                         separados ("tipo"), para graficarlos lado
                                         a lado.
* business.report.dashboard.trend       Por semana y proyecto: balance de costos
                                         (planeado − real) y venta semanal NeoData,
                                         en renglones separados ("serie"), para la
                                         gráfica de tendencia.
"""
from odoo import fields, models, tools

from .const import COST_PARTIDA_SELECTION, WEEK_STATE_SELECTION


class BusinessReportWeekPartidaSummary(models.Model):
    _name = 'business.report.week.partida.summary'
    _description = 'Balance de costos por partida de la semana'
    _auto = False
    _order = 'week_date desc, sequence'

    week_id = fields.Many2one('business.report.week', string='Semana', readonly=True)
    week_date = fields.Date(string='Fecha de corte', readonly=True)
    week_state = fields.Selection(WEEK_STATE_SELECTION, string='Estado', readonly=True)
    is_current = fields.Boolean(string='Semana vigente', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    partida = fields.Selection(COST_PARTIDA_SELECTION, string='Partida', readonly=True)
    sequence = fields.Integer(readonly=True)
    project_count = fields.Integer(string='Proyectos', readonly=True)
    planned_amount = fields.Monetary(string='Planeado', readonly=True)
    real_amount = fields.Monetary(string='Real', readonly=True)
    deviation = fields.Monetary(string='Diferencia', readonly=True,
                                help='Planeado − real. Positivo = optimización.')
    deviation_pct = fields.Float(string='%', readonly=True, aggregator=None)
    planned_delta = fields.Monetary(string='Δ planeado vs sem. ant.', readonly=True)
    real_delta = fields.Monetary(string='Δ real vs sem. ant.', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    MIN(p.id) AS id,
                    p.week_id,
                    w.date AS week_date,
                    w.state AS week_state,
                    COALESCE(w.is_current, FALSE) AS is_current,
                    w.company_id,
                    c.currency_id,
                    p.partida,
                    MIN(p.sequence) AS sequence,
                    COUNT(DISTINCT p.project_line_id) AS project_count,
                    SUM(p.planned_amount) AS planned_amount,
                    SUM(p.real_amount) AS real_amount,
                    SUM(p.planned_amount) - SUM(p.real_amount) AS deviation,
                    CASE WHEN SUM(p.planned_amount) <> 0
                         THEN (SUM(p.planned_amount) - SUM(p.real_amount)) / SUM(p.planned_amount)
                         ELSE 0 END AS deviation_pct,
                    SUM(p.planned_delta) AS planned_delta,
                    SUM(p.real_delta) AS real_delta
                FROM business_report_week_partida p
                JOIN business_report_week w ON w.id = p.week_id
                JOIN res_company c ON c.id = w.company_id
                GROUP BY p.week_id, w.date, w.state, w.is_current, w.company_id, c.currency_id, p.partida
            )
        """ % self._table)


class BusinessReportDashboardCost(models.Model):
    _name = 'business.report.dashboard.cost'
    _description = 'Tablero de Dirección · costo planeado y real por partida'
    _auto = False
    _order = 'week_date desc, sequence, kind'

    week_id = fields.Many2one('business.report.week', string='Semana', readonly=True)
    week_date = fields.Date(string='Fecha de corte', readonly=True)
    is_current = fields.Boolean(string='Semana vigente', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Proyecto', readonly=True)
    partida = fields.Selection(COST_PARTIDA_SELECTION, string='Partida', readonly=True)
    sequence = fields.Integer(readonly=True)
    kind = fields.Selection([('1_planned', 'Planeado (NeoData)'), ('2_real', 'Real (Odoo)')],
                            string='Tipo', readonly=True)
    amount = fields.Float(string='Importe', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT p.id * 2 - 1 AS id, p.week_id, w.date AS week_date,
                       COALESCE(w.is_current, FALSE) AS is_current, w.company_id,
                       p.analytic_account_id, p.partida, p.sequence,
                       '1_planned' AS kind, p.planned_amount AS amount
                FROM business_report_week_partida p
                JOIN business_report_week w ON w.id = p.week_id
                UNION ALL
                SELECT p.id * 2 AS id, p.week_id, w.date AS week_date,
                       COALESCE(w.is_current, FALSE) AS is_current, w.company_id,
                       p.analytic_account_id, p.partida, p.sequence,
                       '2_real' AS kind, p.real_amount AS amount
                FROM business_report_week_partida p
                JOIN business_report_week w ON w.id = p.week_id
            )
        """ % self._table)


class BusinessReportDashboardTrend(models.Model):
    _name = 'business.report.dashboard.trend'
    _description = 'Tablero de Dirección · balance de costos y venta semanal'
    _auto = False
    _order = 'week_date, serie'

    week_id = fields.Many2one('business.report.week', string='Semana', readonly=True)
    week_date = fields.Date(string='Fecha de corte', readonly=True)
    week_state = fields.Selection(WEEK_STATE_SELECTION, string='Estado', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Proyecto', readonly=True)
    serie = fields.Selection([('1_balance', 'Balance de costos (planeado − real)'),
                              ('2_sale', 'Venta semanal (avance NeoData)')],
                             string='Serie', readonly=True)
    amount = fields.Float(string='Importe', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT l.id * 2 - 1 AS id, l.week_id, w.date AS week_date, w.state AS week_state,
                       w.company_id, l.analytic_account_id,
                       '1_balance' AS serie, l.deviation AS amount
                FROM business_report_week_project l
                JOIN business_report_week w ON w.id = l.week_id
                UNION ALL
                SELECT l.id * 2 AS id, l.week_id, w.date AS week_date, w.state AS week_state,
                       w.company_id, l.analytic_account_id,
                       '2_sale' AS serie, l.neodata_advance AS amount
                FROM business_report_week_project l
                JOIN business_report_week w ON w.id = l.week_id
            )
        """ % self._table)
