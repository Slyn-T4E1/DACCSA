# custom_business_reports · Reportes de dirección y comerciales

Autor: Slyn · Odoo 19 Enterprise (Odoo.sh) · Cliente: DACSA

El desarrollo se entrega por etapas para probar poco a poco. Cada etapa sube
la versión del módulo y se prueba en la base de pruebas antes de seguir.

| Etapa | Versión | Contenido | Se prueba con |
|---|---|---|---|
| 1 | 19.0.1.0.0 | Base comercial en CRM: segmento por calidad del lead, grupo de etapa, fecha de cierre editable y automática en Cancelado, último movimiento y días sin movimiento, filtros y columnas | Mauricio |
| 2 | 19.0.2.0.0 | Tablero comercial en Tableros (KPIs, invitaciones por mes y trimestre, ganados/perdidos, venta por mes de cierre) y listados por estatus | Mauricio y Ricardo |
| 3 | 19.0.3.0.0 | Construcción · base: tipo de partida en posiciones presupuestarias, semanas de reporte, proyectos en análisis y captura semanal con foto del real al cerrar | César |
| 4 | 19.0.4.0.0 | Construcción · cálculos y detalle por proyecto: balance financiero, márgenes, costos por partida, semana vs anterior, apuntes que forman el real | César |
| 5 | 19.0.5.0.0 | Tablero de Dirección (resumen de todos los proyectos en análisis) | Ricardo y César |
| 6 | 19.0.6.0.0 | PDF Reporte Semanal de Dirección y ajustes finales | Dirección |

## Etapa 1 · Qué hace

* **Segmento** (`report_segment`): Sin recompra / Recompra / Inadecuado, desde el
  campo Studio `x_studio_calidad_del_lead`. Reglas en *CRM › Configuración ›
  Segmentos por calidad del lead*.
* **Grupo de etapa** (`report_stage_group`): se configura en cada etapa
  (*CRM › Configuración › Etapas*). Al instalar se asigna solo por nombre.
* **Fecha de cierre** (`date_closed`): editable cuando la oportunidad está
  cerrada y con historial. Se llena sola al entrar a etapas marcadas con
  "Registrar fecha de cierre al entrar" (Cancelado).
* **Último movimiento** (`report_last_move_date`) y **días sin movimiento**
  con semáforo (30 / 90 días). Cuenta cambios, mensajes, notas y actividades.
* Filtros y agrupaciones nuevas en la búsqueda de oportunidades.

## Etapa 1 · Cómo probar

1. Instalar el módulo y revisar en el log los mensajes "Etapa ...: grupo de reporte".
2. *CRM › Configuración › Etapas*: confirmar el grupo de cada etapa y que
   "Cancelado" registre fecha de cierre.
3. *CRM › Configuración › Segmentos por calidad del lead*: confirmar las 4 reglas.
4. Lista de oportunidades, filtro "Cuenta para tableros" y agrupar por
   Segmento: los totales deben coincidir con la calidad del lead.
5. Abrir una oportunidad ganada, pestaña "Seguimiento y reportes": cambiar la
   fecha de cierre y ver el registro en el chatter.
6. Mover una oportunidad a Cancelado: debe tomar fecha de cierre.
7. Filtro "Sin movimiento más de 90 días": revisar que sean oportunidades
   realmente detenidas.
