{
    "name": "Custom Budget Project - Presupuestos v17 en Proyectos",
    "summary": "Comportamiento del presupuesto analítico de Odoo 17 (posiciones presupuestarias) "
    "sobre base_account_budget, reflejado en el tablero de proyectos",
    "description": """
Complementa el módulo base_account_budget (Cybrosys) para que funcione como el
presupuesto analítico de Odoo 17 (account_budget + project_account_budget):

* Importe real calculado igual que v17: columna del plan analítico correcto,
  apuntes contables cuando la línea no tiene cuenta analítica y todas las
  partidas analíticas cuando la posición presupuestaria no tiene cuentas.
* Importe teórico, % de logro, fecha de pago, nombre de la línea, botón
  "Apuntes..." y validaciones de v17.
* Tablero del proyecto (panel derecho): sección Presupuestos agrupada por
  posición presupuestaria, con previsto, real y diferencia; botón para agregar
  presupuesto; indicador $ en el kanban y resumen en la actualización del proyecto.
* Restaura la relación posición presupuestaria → cuentas contables de v16.
""",
    "version": "19.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "AKRON",
    "license": "LGPL-3",
    "depends": ["base_account_budget", "project_account_budget"],
    "data": [
        "views/budget_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "custom_budget_project/static/src/project_right_side_panel/*",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
