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
| 6 | 19.0.6.0.0 | App "Tableros DACSA": tableros en JavaScript configurables (filtros, dominios, medidas y fórmulas); reemplaza los tableros de la app Tableros | Dirección, Mauricio |
| 7 | 19.0.7.0.0 | PDF Reporte Semanal de Dirección (resumen + sección por proyecto), guardado en la semana y envío por correo | Dirección |
| 7+ | 19.0.8.0.0 | Tabla "Invitaciones a cotizar, mes a mes" (meses en columnas), metas de venta mensuales configurables (Meta, Avance, Venta vs meta) y antigüedad del pipeline por rangos | Mauricio y Dirección |
| 7+ | 19.0.9.0.0 | "Listados comerciales" como el Reporte Comercial: ganados SR/R (semanas creación→cierre), perdidos, cancelados, en pausa, pipeline abierto y prospección, cada uno con indicadores, gráfica y listado | Mauricio |
| 7+ | 19.0.10.0.0 | "Seguimiento comercial" como el Reporte Comercial: resumen ejecutivo con SR/R, histórico de invitaciones con indicadores, embudo Totales / SR / R, venta por trimestre vs meta acumulada, ingenierías y origen de leads | Mauricio y Dirección |

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

## Etapa 6 · Qué hace

App propia **Tableros DACSA** (ícono en el menú principal) con tres tableros de fábrica:

| Tablero | Categoría | Lo ven |
|---|---|---|
| Seguimiento comercial | Comercial | Ventas (vendedores) |
| Listados comerciales | Comercial | Ventas (vendedores) |
| Reporte semanal Dirección | Dirección | Proyecto (usuarios) |

En pantalla:

- Menú lateral con los tableros por categoría (se puede ocultar).
- Filtros arriba: periodo (con fechas libres), registros (vendedor, semana, proyecto), selección (segmento) o texto (cliente). "Valores por omisión" los regresa a su estado inicial.
- Indicadores, gráficas (barras, apiladas, horizontales, línea, pastel, dona), tablas ordenables con búsqueda y renglón de total, y listados.
- Clic en un indicador, barra o renglón abre los registros que forman ese valor; en listados abre el registro.
- El Reporte semanal Dirección abre en la semana vigente; se puede elegir cualquier otra semana. El botón **Tablero** de cada semana lo abre en esa semana.

Configuración (grupo **Tableros DACSA: administrador**; los administradores de Odoo lo tienen):

- Botón **Configurar** (tablero completo), **Elemento** (agregar) y el lápiz de cada elemento.
- Tablero: nombre, categoría, grupos que lo ven, filtros y elementos.
- Filtro: tipo, campo por omisión, modelo de los registros, dominio de los registros que se pueden elegir y valor por omisión (dominio; p. ej. la semana vigente).
- Elemento: modelo, **dominio** (editor de dominios de Odoo), agrupación (con intervalo de fecha), series, orden, límite, formato, colores, umbral y formulario de detalle. Pestaña "Filtros aplicados" para usar otro campo o no aplicar un filtro.
- Medidas: suma, promedio, mínimo, máximo o conteo de un campo, con dominio adicional y campo de fecha propio para el periodo; o **fórmula** con los códigos de otras columnas o indicadores. Funciones: div(a, b), abs, min, max, round.
- La vista previa del elemento muestra su valor con los filtros por omisión; los errores de dominio o fórmula se muestran en el propio elemento sin romper el tablero.
- Las actualizaciones del módulo no sobrescriben los tableros (se crean una sola vez).

Ya no se usa la app Tableros de Odoo (hoja de cálculo): sus tableros "Seguimiento comercial", "Listados comerciales" y "Reporte semanal Dirección" se quitan al actualizar.

## Etapa 6 · Cómo probar

1. Abrir la app Tableros DACSA y revisar los tres tableros contra las cifras que ya se validaron.
2. Cambiar filtros (periodo, vendedor, segmento, semana, proyecto) y dar clic en valores para ver el detalle.
3. Con un administrador: lápiz en un indicador, cambiar el dominio o la fórmula, guardar y ver el cambio.
4. Crear un tablero nuevo desde Configuración con un filtro y un par de elementos.
5. Entrar con un vendedor: solo ve los tableros comerciales y no ve los botones de configuración.

## Etapa 7 · Qué hace

PDF **Reporte Semanal de Dirección** en hojas 16:9 (como el PowerPoint), con el pie "Propiedad de DACCSA – Uso Restringido · CON-FO-17 Rev.00".

En la semana: botón **Reporte PDF** (asistente) y, en semanas cerradas, **Enviar a Dirección** (correo con el PDF adjunto). También desde Imprimir › Reporte Semanal de Dirección.

Asistente: Resumen de Dirección (sí/no), una sección por proyecto (sí/no) y qué proyectos llevar.

Contenido:

1. Portada (logo de la compañía, fecha de corte).
2. Indicadores (costo planeado, real, desviación, vs semana anterior, venta semanal, margen operativo) y proyectos en análisis agrupados por cliente.
3. Balance de costos por partida (gráfica + tabla con diferencias vs semana anterior).
4. Indicadores de costos y venta (últimas 6 semanas).
5. Margen operativo al momento – proyectos (rojo bajo la alerta de margen).
6. Por proyecto: portada, balance financiero (estimaciones y margen NeoData por semana), costos (planeado vs real por partida + tendencia) y semana (margen semanal y diferencia de costos).

Semana cerrada: el PDF se guarda en la semana (campo "Último PDF" y en el historial). Semana en captura: vista previa con marca de agua, no se guarda.

Pendiente: lámina de Flujo (falta definir con DACSA qué comparan las dos columnas).

Ajuste de permisos de la Etapa 6 incluido: los usuarios que no son administradores ya calculan los tableros (la configuración se lee como superusuario; los datos con los permisos del usuario).

## Etapa 7 · Cómo probar

1. Semana en captura › Reporte PDF › Generar PDF: sale la vista previa con marca de agua.
2. Cerrar la semana › Reporte PDF: el PDF se descarga y queda adjunto en la semana.
3. Enviar a Dirección: se abre el correo con el PDF adjunto.
4. Revisar que cada hoja ocupe la página completa y que las cifras coincidan con la pestaña Resumen y el tablero.

## 19.0.8.0.0 · Qué hace

Tablero **Seguimiento comercial** (se agrega solo a los tableros que ya existen, sin tocar lo que el usuario cambió):

1. **Invitaciones a cotizar, mes a mes**: tabla con los meses en columnas (por fecha de creación) y el Total al final. Renglones: invitaciones, atendidos nuevos (Sin recompra), atendidos recompra, atendidos otros (inadecuado / sin segmento) y no atendidos, cada uno con su % sobre las invitaciones. Clic en un número = oportunidades de ese mes y estatus.
2. **Metas de venta mensuales** (CRM › Configuración › Metas de venta mensuales, o Tableros DACSA › Configuración › Metas de venta): un renglón por mes y empresa; la fecha se guarda como día 1.
   - Indicador **Meta de venta** = Σ metas de los meses del periodo filtrado.
   - Indicador **Avance vs meta** = venta ganada / meta (rojo si es menor al 100 %).
   - Gráfica **Venta por mes de cierre vs meta mensual**: barras de venta ganada y la meta como línea.
   - La meta es de la empresa: no cambia con el filtro de vendedor ni de segmento.
3. **Pipeline abierto por antigüedad**: gráfica (barras = oportunidades, línea en el eje derecho = monto) y tabla por rangos de días desde la creación: 0–30, 31–60, 61–90, 91–180 y más de 180. Solo enviadas pendientes de respuesta, a hoy.

Nuevo en la configuración de elementos (para armar otros sin programar):

- Tabla › Formato › **Grupos en columnas**.
- Datos › **Rangos de antigüedad desde** (campo de fecha) y **Rangos (días)**, p. ej. `30,60,90,180`.
- Medida › **Datos de otro modelo** + **Agrupar por (otro modelo)**: p. ej. la meta (Meta de venta mensual, campo `date`) junto a la venta por mes.
- Medida › **Dibujar como** (barras o línea) y **Eje derecho**.

## 19.0.8.0.0 · Cómo probar

1. CRM › Configuración › Metas de venta mensuales: capturar la meta de cada mes del año.
2. Tableros DACSA › Seguimiento comercial: revisar Meta de venta y Avance vs meta con el periodo "Este año" y "Este mes".
3. Comparar la tabla mes a mes contra la gráfica "Invitaciones a cotizar por mes" (mismos números) y dar clic en una celda.
4. Revisar la gráfica de venta vs meta y la de antigüedad; clic en una barra abre las oportunidades del rango.

## 19.0.9.0.0 · Qué hace

Tablero **Listados comerciales** rearmado como las láminas 4 a 9 del Reporte Comercial. Cada sección trae indicadores Sin Recompra / Recompra (número · monto), su gráfica y su listado:

| Sección | Indicadores | Gráfica | Listado |
|---|---|---|---|
| Proyectos ganados | Ganados SR y R (ticket y semanas), venta, semanas creación→cierre | — | Dos listados (SR y R) con #, creado, cierre, semanas, cliente, proyecto, monto y total |
| Proyectos perdidos | Perdidos SR, R y total | Razones de pérdida | Perdidos por monto con SR/R y razón |
| Proyectos cancelados | Cancelados SR, R y total (por fecha de creación) | Cancelados por mes de creación | Cancelados por monto |
| Proyectos en pausa | En pausa SR, R y total (solo con monto) | Antigüedad 0–90, 91–180, 181–365, más de 365 días | En pausa por monto con días (rojo: más de un año) |
| Pipeline abierto | Enviadas (SR/R), Por enviar, En pausa, Enviadas con más de 180 días | Antigüedad de enviadas (# y monto) + tabla por rango | Enviadas por monto con días (rojo: más de 90) |
| Prospección Sin Recompra | — | Leads por mes de creación y etapa | Leads de los últimos 3 meses agrupados por etapa, con origen |

"Sin Recompra" incluye Inadecuado y sin segmento (como el reporte de Mauricio). Se agrega el campo **Semanas creación→cierre** en la oportunidad.

Nuevo en la configuración (para cualquier tablero):

- Título o nota con valores: `{código}` se cambia por el valor del indicador, p. ej. `SR {env_sr} ({env_sr_monto})`.
- Indicador › **Segundo valor**: muestra "número · monto".
- Gráfica › **Números sobre las barras**.
- Listado › **Columnas** con encabezado propio (`date_closed:Cierre`), **Agrupar listado por**, **Resaltar en rojo** (`report_age_days > 90`), **Numerar renglones** y **Renglón de total** (de todos los registros del filtro).
- Formato **Número (1 decimal)**.
- Dominios con fechas relativas: `context_today()` y `relativedelta`.

Al actualizar se quitan los 5 listados anteriores de "Listados comerciales" (ganados, perdidos, pipeline, pausa y cancelados) y se agregan las secciones nuevas; "Oportunidades lentas" se queda al final.

## 19.0.9.0.0 · Cómo probar

1. Tableros DACSA › Listados comerciales con "Este año": comparar cada sección contra las láminas 4 a 9 del PDF (p. ej. perdidos SR 16 · $737.9 M, R 14 · $141.8 M; en pausa con monto SR 8 · $222.9 M, R 6 · $132.4 M).
2. Clic en una barra o en un renglón abre las oportunidades.
3. Pipeline abierto y En pausa no cambian con el periodo (son a hoy).

## 19.0.10.0.0 · Qué hace

Tablero **Seguimiento comercial** como las láminas 0 a 4 y 10 del Reporte Comercial:

1. **Resumen ejecutivo** (3 renglones de indicadores): venta ganada (SR · R), avance vs meta, meta, pipeline enviado (cotizaciones y cuántas con más de 180 días), ganados y perdidos (SR · R), efectividad (SR · R), **semana** (venta, ganados, perdidos y leads nuevos de los últimos 7 días), invitaciones, atendidas (% de las invitaciones), % de bateo (SR · R · base histórica) y **semanas creación→cierre**.
2. **Invitaciones a cotizar**: gráficas por mes e histórico por trimestre, y 4 indicadores del histórico (cotizados, declinados, % de bateo histórico SR/R y trimestre en curso vs anterior). Sigue la tabla mes a mes.
3. **Ganados, perdidos y venta**: gráfica de ganados y perdidos por mes junto al **embudo Totales / Sin Recompra / Recompra** (invitaciones, atendidos, declinados, ganados, perdidos y pendientes con su %, % de bateo, efectividad y % de bateo histórico); indicadores **Venta Sin Recompra** y **Recompra** (proyectos, % y ticket), **Ticket promedio** e **Ingenierías** (nombre contiene "ingenier"); **venta por trimestre vs meta acumulada** (venta, acumulado y meta acumulada) junto a la venta por mes.
4. **Origen de leads Sin Recompra** (si existe el campo de Studio "¿Cómo se generó el lead?"): barras de leads, cotizados y ganados por canal y tabla con % cotizado y % ganado.

El "Embudo por segmento" anterior se reemplaza por el embudo Totales / SR / R. Al actualizar solo se cambian las notas de fábrica que el usuario no modificó.

Nuevo en la oportunidad: **Segmento (SR/R)** (Recompra o Sin Recompra, que incluye Inadecuado y sin segmento).

Nuevo en las medidas: **Acumulada** (suma corrida por grupo) y **Sin periodo** (no aplica el filtro de periodo, p. ej. para un histórico).

## 19.0.10.0.0 · Cómo probar

1. Seguimiento comercial con "Este año": comparar el resumen contra la hoja "Resumen ejecutivo" del PDF y el embudo contra la tabla de la lámina 3.
2. Capturar las metas del año y revisar "Venta por trimestre vs meta acumulada".
3. Revisar la sección "Origen de leads Sin Recompra" contra la lámina 10.

### 19.0.10.0.1

- Origen de leads Sin Recompra igual que la lámina 10: Sin Recompra incluye Inadecuado, sin "Ganados en 0's" y sin leads sin origen o con origen "Recompra".
- La barra "Acumulado" de la venta por trimestre pasa a gris para que se vea en modo oscuro.
