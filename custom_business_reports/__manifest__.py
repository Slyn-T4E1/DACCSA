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
""",
    'version': '19.0.2.0.0',
    'category': 'Sales/CRM',
    'author': 'Slyn',
    'license': 'LGPL-3',
    # Etapa 1: CRM. Etapa 2: Tableros (spreadsheet_dashboard).
    # Las siguientes etapas agregarán proyectos y presupuestos por posición.
    'depends': ['crm', 'mail', 'spreadsheet_dashboard'],
    'data': [
        'security/ir.model.access.csv',
        'views/crm_stage_views.xml',
        'views/crm_lead_views.xml',
        'views/crm_lead_segment_rule_views.xml',
        'views/business_reports_views.xml',
        'views/menus.xml',
        'data/spreadsheet_dashboard.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
