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
| 4 | 19.0.4.0.0 | Construcción · cálculos y detalle por proyecto: valor contrato, estimado autorizado y facturado desde Odoo, balance financiero, márgenes, costos por partida, semana vs anterior, histórico y apuntes | César |
| 5 | 19.0.5.0.0 | Tablero de Dirección: semana vigente, tablero en Tableros, pestaña Resumen por semana, gráficas de costos y tendencia, alerta de margen bajo | Ricardo y César |
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

## Etapa 3 · Qué hace

* **Tipo de partida** en las posiciones presupuestarias (`report_partida`):
  Materiales, Mano de obra, Subcontratistas, Equipo y herramienta,
  Indirectos, Ventas u Otro. Se asigna solo por el nombre (Materiales PM,
  Mano de Obra NMM...) y se revisa en *Proyecto › Configuración › Partidas de
  posiciones presupuestarias* (filtro "Sin tipo de partida").
* **Semanas de reporte** (*Proyecto › Reportes › Reporte semanal Dirección ›
  Semanas de reporte*): Borrador → En captura → Cerrada.
  * *Iniciar captura*: copia los proyectos de la semana anterior con su venta
    NeoData (pasa a "semana anterior"), costos planeados y reales anteriores.
  * Captura en una sola pantalla: una fila por proyecto (cuenta analítica)
    con venta NeoData; botón *Partidas* para el costo planeado por partida y
    OC / estimación en revisión.
  * *Actualizar real*: costo real por partida hasta la fecha de corte, con la
    misma lógica que el Real del presupuesto por posición.
  * *Cerrar semana*: exige todos los proyectos capturados y congela el real.
    Solo el gerente de proyectos puede reabrir.
  * Cálculos: avance semanal NeoData, costo de la semana, diferencia semanal,
    margen NeoData, desviación (planeado − real) por proyecto y por partida.
  * Botón *Apuntes* en cada partida: apuntes analíticos que forman el real.

## Etapa 3 · Cómo probar

1. Actualizar el módulo (migración 19.0.3.0.0: tipo de partida por nombre).
2. *Partidas de posiciones presupuestarias*: filtro "Sin tipo de partida" y
   asignar a mano las que no se reconocieron.
3. Crear la semana con fecha de corte, *Iniciar captura* y agregar los proyectos
   en análisis (la primera vez; después se copian solos).
4. Abrir *Partidas* de MARS Patio de Maniobras: el real por partida debe
   coincidir con el Real de "Presupuestos por posición presupuestaria" del
   tablero del proyecto (si el presupuesto cubre hasta la fecha de corte).
5. Capturar venta NeoData y planeado; cerrar la semana; crear la siguiente y
   revisar que arrastre los valores y calcule el costo de la semana.

## Etapa 4 · Qué hace

Detalle por proyecto (botón **Detalle** en la semana, o Proyecto › Reportes › Reporte semanal Dirección › **Proyectos en análisis**).

Datos que se toman de Odoo con **Actualizar real**, hasta la fecha de corte, y que se congelan al cerrar la semana:

| Dato | De dónde sale |
|---|---|
| Valor contrato | Líneas de pedidos de venta confirmados con la cuenta analítica del proyecto (fecha del pedido ≤ corte), sin impuestos y sin líneas de anticipo, según el % de la distribución analítica |
| Estimado autorizado | Apuntes analíticos del proyecto en las cuentas de la posición de Ventas, sin las cuentas marcadas como anticipo de clientes (206.01.01) |
| Facturado | Facturas menos notas de crédito de cliente publicadas del proyecto, sin impuestos y sin cuentas de anticipo |

Cálculos:

- Restante por estimar = valor contrato − estimado autorizado. % Estimado = estimado / contrato.
- Margen operativo al momento = estimado autorizado − costo real (5 partidas). % sobre el estimado.
- Margen NeoData = venta NeoData − costo real (de la Etapa 3).
- % Margen plan: captura manual, se arrastra a la semana siguiente.

Pantalla de detalle:

- Accesos arriba: **Contrato** (pedidos), **Estimado** (apuntes), **Facturado** (líneas de factura).
- Pestañas: **Balance financiero**, **Costos** (planeado vs real por partida con botón Apuntes y tendencia semanal del proyecto) y **Semana** (margen semanal y diferencia de costos por partida contra la semana anterior).
- Botones: **Gráfica de partidas**, **Histórico** (tendencia del proyecto en todas sus semanas) y **Presupuesto por posición**.

Configuración: la cuenta 206.01.01 queda marcada como "Anticipo de clientes (reportes)" al instalar o actualizar. Se puede marcar o desmarcar cualquier cuenta en Contabilidad › Configuración › Plan de cuentas.

Dependencia nueva: `sale`.

## Etapa 4 · Cómo probar

1. Abrir una semana en captura y presionar **Actualizar real**.
2. En el proyecto, botón **Detalle**: revisar contrato, estimado, facturado y márgenes.
3. Comparar contra Odoo: Contrato contra los pedidos de venta del proyecto; Estimado contra el real de "Ventas PM" en el presupuesto menos los apuntes de 206.01.01; Facturado contra "Facturas del cliente" en la rentabilidad del proyecto.
4. Abrir **Estimado** y **Facturado** para ver los apuntes; agrupar por cuenta contable.
5. Capturar % margen plan, cerrar la semana y crear la siguiente: el % se arrastra y los datos de la semana cerrada no cambian.

## Etapa 5 · Qué hace

Tablero de Dirección con el resumen de todos los proyectos en análisis.

**Semana vigente**: la última semana cerrada (si aún no hay cerradas, la última semana). Se marca sola al cerrar, reabrir o crear semanas.

**Tablero "Reporte semanal Dirección"** (Tableros › Dirección y comercial, o Proyecto › Reportes › Reporte semanal Dirección › Tablero de Dirección). Muestra la semana vigente:

- Indicadores: costo planeado, costo real, desviación (% de optimización), cambio de la desviación vs la semana anterior, venta semanal (Σ avance NeoData) y margen operativo global.
- Gráfica "Balance de costos por partida": planeado vs real por partida, suma de todos los proyectos.
- Gráfica "Indicadores de costos y venta por semana": balance de costos (planeado − real) y venta semanal de todas las semanas.
- Tabla "Balance de costos por partida" con diferencia, % y cambios contra la semana anterior (verde = optimización, rojo = sobrecosto).
- Tabla "Margen operativo al momento – proyectos": venta real (estimado autorizado), costo real, margen y %; en rojo los proyectos bajo la alerta de margen.
- Filtro "Proyecto" para quitar o dejar solo algunos proyectos.

**Pestaña "Resumen" en cada semana** (sirve para ver semanas anteriores): los mismos indicadores, el balance por partida y el margen por proyecto (con botón Detalle). Botones **Gráfica de costos**, **Tendencia** y **Tablero**. El campo **Alerta de margen bajo** (15 % por omisión) se captura en la semana y pasa a la siguiente.

El tablero se genera con `tools/generate_week_report_dashboard.py`; los cambios hechos en pantalla se pierden al actualizar el módulo.

## Etapa 5 · Cómo probar

1. Cerrar una semana con proyectos capturados: queda como "Semana vigente".
2. Abrir Tableros › Dirección y comercial › Reporte semanal Dirección y comparar los indicadores contra la pestaña Resumen de esa semana.
3. Usar el filtro Proyecto para quitar un proyecto y revisar que cambien las tablas y gráficas.
4. Cambiar la alerta de margen en la semana (antes de cerrarla) y revisar los proyectos en rojo.
5. En una semana anterior, abrir la pestaña Resumen y los botones Gráfica de costos y Tendencia.
