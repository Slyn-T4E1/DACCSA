# custom_business_reports · Reportes de dirección y comerciales

Autor: Slyn · Odoo 19 Enterprise (Odoo.sh) · Cliente: DACSA

Pruebas automáticas: `odoo-bin -d <base> -u custom_business_reports --test-tags /custom_business_reports`

El desarrollo se entrega por etapas para probar poco a poco. Cada etapa sube
la versión del módulo y se prueba en la base de pruebas antes de seguir.

| Etapa | Versión | Contenido | Se prueba con |
|---|---|---|---|
| 1 | 19.0.1.0.0 | Base comercial en CRM: segmento por calidad del lead, grupo de etapa, fecha de cierre editable y automática en Cancelado, último movimiento y días sin movimiento, filtros y columnas | Mauricio |
| 2 | 19.0.2.0.0 | Seguimiento comercial: menú CRM › Reportes › Seguimiento comercial (gráficas y listados) y tableros "Seguimiento comercial" y "Listados comerciales" en Tableros | Mauricio y Ricardo |
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
   Las que ya estaban en Cancelado al instalar toman como fecha de cierre la
   de su último cambio de etapa (se puede corregir a mano).
7. Filtro "Sin movimiento más de 90 días": revisar que sean oportunidades
   realmente detenidas.

## Etapa 2 · Qué hace

* **Campos nuevos** en la oportunidad (calculados y guardados):
  * `report_invitation_status`: Atendido · Sin recompra / Recompra / Inadecuado,
    o No atendido (no se participó).
  * `report_close_status`: Ganado o Perdido · Sin recompra / Recompra / Otro.
    "Ganados en 0's" queda fuera.
  * `report_open_status` (desde la etapa): Enviada (pipeline abierto) o En pausa.
* **Menú CRM › Reportes › Seguimiento comercial**:
  * Gráficas: Invitaciones a cotizar (por mes de creación, apiladas),
    Ganados y perdidos (por mes de cierre), Venta por mes de cierre (monto).
  * Listados: Proyectos ganados (agrupados por segmento), perdidos,
    cancelados, en pausa, pipeline abierto (enviadas), invitaciones por
    enviar, prospección (por etapa) y oportunidades lentas (+90 días).
* **Tableros › Dirección y comercial**:
  * "Seguimiento comercial": indicadores (venta, ganados, % de bateo,
    efectividad, pipeline enviado, invitaciones), 6 gráficas y el embudo por
    segmento. Filtros: Periodo y Vendedor.
  * "Listados comerciales": los 6 listados con los 15 registros principales.
  * Se generan con `tools/generate_commercial_dashboard.py`; no editar el JSON
    a mano. Al actualizar el módulo se reemplazan con la versión del código.

## Etapa 2 · Cómo probar

1. Actualizar el módulo (corre la migración 19.0.2.0.0: marca Enviada y En Pausa).
2. *CRM › Configuración › Etapas*: Enviada y En Pausa con "Listado del pipeline".
3. *CRM › Reportes › Seguimiento comercial › Invitaciones a cotizar*: cambiar a
   tabla dinámica y comparar el total por trimestre con el reporte de Mauricio.
4. *Proyectos ganados*: los totales por segmento deben sumar la venta del año.
5. *Tableros › Dirección y comercial › Seguimiento comercial*: cambiar el Periodo
   y el Vendedor; los indicadores y el embudo deben moverse juntos.
6. Clic en una gráfica: abre el menú del reporte correspondiente.
