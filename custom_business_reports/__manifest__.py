# -*- coding: utf-8 -*-
{
    'name': 'Reportes de dirección y comerciales',
    'summary': 'Reporte Semanal de Dirección (construcción) y seguimiento comercial del CRM para DACSA',
    'description': """
Reportes de dirección y comerciales (DACSA).

Se entrega por etapas (ver README.md).

Etapa 1, base comercial en el CRM: segmento por calidad del lead, grupo de
etapa para reportes, fecha de cierre editable y automática en Cancelado,
último movimiento y días sin movimiento.

Etapa 2, seguimiento comercial: menú CRM > Reportes > Seguimiento comercial
(gráficas y listados por estatus) y tablero "Seguimiento comercial" en
Tableros.

Etapa 3, Reporte Semanal de Dirección (base): tipo de partida en las
posiciones presupuestarias y semanas de reporte con proyectos en análisis,
captura de NeoData y foto del costo real al cerrar la semana.

Etapa 4, detalle por proyecto: valor contrato, estimado autorizado y
facturado desde Odoo, balance financiero, margen operativo, costos por
partida, semana actual vs anterior, histórico y accesos a los apuntes.

Etapa 5, Tablero de Dirección: semana vigente, pestaña "Resumen" en cada
semana (balance de costos por partida y margen operativo por proyecto),
gráficas de costos y tendencia.

Etapa 6, app "Tableros DACSA": tableros en JavaScript (comercial, listados y
Reporte semanal Dirección) configurables desde la app: filtros, dominios,
medidas y fórmulas.

Etapa 7, PDF "Reporte Semanal de Dirección": hojas 16:9 con el resumen y una
sección por proyecto; se guarda en la semana cerrada y se envía por correo.
""",
    'version': '19.0.7.0.1',
    'category': 'Sales/CRM',
    'author': 'Slyn',
    'license': 'LGPL-3',
    # Etapa 1: CRM. Etapa 2: Tableros (spreadsheet_dashboard).
    # Etapa 3: proyectos y presupuestos por posición (base_account_budget).
    # Etapa 4: pedidos de venta para el valor contrato (sale).
    # Etapa 6: los tableros dejan de usar la app Tableros (spreadsheet_dashboard).
    'depends': ['crm', 'mail', 'project', 'analytic', 'base_account_budget', 'sale', 'web'],
    'data': [
        'security/business_dashboard_security.xml',
        'security/ir.model.access.csv',
        'views/crm_stage_views.xml',
        'views/crm_lead_views.xml',
        'views/crm_lead_segment_rule_views.xml',
        'views/business_reports_views.xml',
        'views/account_budget_post_views.xml',
        'views/business_report_week_views.xml',
        'views/business_dashboard_views.xml',
        'views/business_report_week_print_views.xml',
        'views/menus.xml',
        'report/week_direction_report.xml',
        'report/week_direction_mail.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_business_reports/static/src/dashboard/**/*',
        ],
        'web.report_assets_common': [
            'custom_business_reports/static/src/report/week_direction_report.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
