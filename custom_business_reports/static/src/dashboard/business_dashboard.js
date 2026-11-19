/** @odoo-module **/
/**
 * Tableros DACSA (Etapa 6): acción cliente que pinta los tableros configurables.
 *
 * El cálculo se hace en Python (business.dashboard.get_dashboard_data); aquí
 * solo se dibuja: menú de tableros, barra de filtros, indicadores, gráficas
 * (Chart.js de Odoo), tablas ordenables con búsqueda y listados. Clic en un
 * valor, barra o renglón abre los registros que lo forman. Los
 * administradores pueden editar cada elemento o el tablero completo.
 */
import { Component, onWillStart, onWillUnmount, useRef, useState, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { router } from "@web/core/browser/router";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { useSetupAction } from "@web/search/action_hook";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { RecordSelector } from "@web/core/record_selectors/record_selector";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";

// ---------------------------------------------------------------------------
// Formato de números
// ---------------------------------------------------------------------------
function formatValue(value, format, { abbreviate = false, currency = { symbol: "$", position: "before" } } = {}) {
    const number = Number(value || 0);
    if (format === "percent") {
        return `${(number * 100).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %`;
    }
    const abs = Math.abs(number);
    const sign = number < 0 ? "-" : "";
    let text;
    if (abbreviate && abs >= 1e6) {
        text = `${(abs / 1e6).toLocaleString("es-MX", { maximumFractionDigits: abs >= 1e8 ? 0 : 1 })} M`;
    } else if (abbreviate && abs >= 1e4) {
        text = `${(abs / 1e3).toLocaleString("es-MX", { maximumFractionDigits: 0 })} k`;
    } else if (format === "integer" || (format === "number" && Number.isInteger(abs))) {
        text = abs.toLocaleString("es-MX", { maximumFractionDigits: 0 });
    } else {
        text = abs.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (format === "monetary") {
        return currency.position === "after" ? `${sign}${text} ${currency.symbol}` : `${sign}${currency.symbol}${text}`;
    }
    return `${sign}${text}`;
}

// ---------------------------------------------------------------------------
// Gráfica (Chart.js)
// ---------------------------------------------------------------------------
class DashboardChart extends Component {
    static template = "custom_business_reports.DashboardChart";
    static props = { widget: Object, currency: Object, onClick: Function };

    setup() {
        this.canvasRef = useRef("canvas");
        onWillStart(() => loadBundle("web.chartjs_lib"));
        // Se vuelve a dibujar cada vez que cambian los datos del elemento
        useEffect(() => {
            this.renderChart();
            return () => this.chart?.destroy();
        }, () => [this.props.widget]);
        onWillUnmount(() => this.chart?.destroy());
    }

    renderChart() {
        if (!this.canvasRef.el) {
            return;
        }
        this.chart?.destroy();
        const w = this.props.widget;
        const pie = ["pie", "doughnut"].includes(w.chart_type);
        const type = pie ? w.chart_type : w.chart_type === "line" ? "line" : "bar";
        const fmt = (v) => formatValue(v, w.format, { abbreviate: true, currency: this.props.currency });
        // Colores de textos y líneas según el tema (claro u oscuro) de Odoo
        const textColor = getComputedStyle(this.canvasRef.el).color || "#374151";
        const gridColor = "rgba(128, 128, 128, 0.2)";
        const palette = w.datasets.map((d) => d.color);
        const datasets = w.datasets.map((d) => ({
            label: d.label,
            data: d.data,
            backgroundColor: pie ? palette.concat(["#93C5FD", "#FCA5A5", "#FCD34D", "#6EE7B7"]) : d.color,
            borderColor: pie ? "#fff" : d.color,
            borderWidth: type === "line" ? 2 : 1,
            fill: false,
            tension: 0.25,
            _measure: d.measure_id,
            _group2: d.group2,
        }));
        this.chart = new window.Chart(this.canvasRef.el, {
            type,
            data: { labels: w.labels, datasets },
            options: {
                maintainAspectRatio: false,
                indexAxis: w.chart_type === "hbar" ? "y" : "x",
                color: textColor,
                plugins: {
                    legend: { display: w.legend, position: "top", labels: { color: textColor } },
                    tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${fmt(ctx.raw)}` } },
                },
                scales: pie ? {} : {
                    x: {
                        stacked: w.chart_type === "bar_stacked",
                        grid: { color: gridColor },
                        ticks: w.chart_type === "hbar" ? { callback: fmt, color: textColor } : { color: textColor },
                    },
                    y: {
                        stacked: w.chart_type === "bar_stacked",
                        grid: { color: gridColor },
                        ticks: w.chart_type === "hbar" ? { color: textColor } : { callback: fmt, color: textColor },
                    },
                },
                onClick: (event, elements) => {
                    if (!elements.length) {
                        return;
                    }
                    const { datasetIndex, index } = elements[0];
                    const dataset = datasets[datasetIndex];
                    this.props.onClick({
                        group_key: w.keys[index],
                        measure_id: dataset._measure,
                        group2_key: dataset._group2,
                    });
                },
            },
        });
    }
}

// ---------------------------------------------------------------------------
// Tabla (ordenable y con búsqueda)
// ---------------------------------------------------------------------------
class DashboardTable extends Component {
    static template = "custom_business_reports.DashboardTable";
    static props = { widget: Object, currency: Object, onRowClick: Function };

    setup() {
        this.state = useState({ search: "", sortIndex: null, sortAsc: false });
    }

    get rows() {
        let rows = this.props.widget.rows;
        const search = this.state.search.trim().toLowerCase();
        if (search) {
            rows = rows.filter((row) => String(row.label).toLowerCase().includes(search));
        }
        if (this.state.sortIndex !== null) {
            const i = this.state.sortIndex;
            const sign = this.state.sortAsc ? 1 : -1;
            rows = [...rows].sort((a, b) => {
                const va = i === -1 ? a.label : a.cells[i].value;
                const vb = i === -1 ? b.label : b.cells[i].value;
                return (va > vb ? 1 : va < vb ? -1 : 0) * sign;
            });
        }
        return rows;
    }

    sortBy(index) {
        if (this.state.sortIndex === index) {
            this.state.sortAsc = !this.state.sortAsc;
        } else {
            this.state.sortIndex = index;
            this.state.sortAsc = index === -1;
        }
    }

    format(value, column) {
        return formatValue(value, column.format, { currency: this.props.currency });
    }

    cellClass(cell) {
        return cell.state === "good" ? "o_bd_good" : cell.state === "bad" ? "o_bd_bad" : "";
    }
}

// ---------------------------------------------------------------------------
// Acción principal
// ---------------------------------------------------------------------------
export class BusinessDashboardAction extends Component {
    static template = "custom_business_reports.BusinessDashboard";
    static components = { ControlPanel, DashboardChart, DashboardTable, MultiRecordSelector, RecordSelector };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.state = useState({
            dashboards: [],
            activeId: null,
            data: null,
            filterValues: {},
            loading: false,
            sidebar: true,
        });
        useSetupAction({
            getLocalState: () => ({ dashboardId: this.state.activeId, filterValues: this.state.filterValues }),
        });
        onWillStart(async () => {
            await this.loadList();
            const saved = this.props.state || {};
            const params = this.props.action.params || {};
            const context = this.props.action.context || {};
            const byXmlid = params.dashboard_xmlid && this.state.dashboards.find((d) => d.xmlid === params.dashboard_xmlid);
            const wanted = saved.dashboardId || params.dashboard_id || byXmlid?.id || context.dashboard_id ||
                router.current.dashboard_id;
            const first = this.state.dashboards[0];
            const id = this.state.dashboards.find((d) => d.id === Number(wanted)) ? Number(wanted) : first?.id;
            this.state.filterValues = saved.filterValues || params.filter_values || {};
            if (id) {
                await this.openDashboard(id, { keepFilters: true });
            }
        });
        useEffect(
            () => router.pushState({ dashboard_id: this.state.activeId }),
            () => [this.state.activeId]
        );
    }

    // ---------------- Datos ----------------
    async loadList() {
        this.state.dashboards = await this.orm.call("business.dashboard", "get_dashboard_list", []);
    }

    get groupedDashboards() {
        const groups = {};
        for (const dashboard of this.state.dashboards) {
            const key = dashboard.category || _t("Tableros");
            (groups[key] = groups[key] || []).push(dashboard);
        }
        return Object.entries(groups).map(([name, items]) => ({ name, items }));
    }

    async openDashboard(id, { keepFilters = false } = {}) {
        if (!keepFilters || id !== this.state.activeId) {
            if (!keepFilters) {
                this.state.filterValues = {};
            }
        }
        this.state.activeId = id;
        await this.reload();
    }

    async reload() {
        if (!this.state.activeId) {
            return;
        }
        this.state.loading = true;
        try {
            const data = await this.orm.call("business.dashboard", "get_dashboard_data",
                [[this.state.activeId]], { filter_values: this.state.filterValues });
            this.state.data = data;
            // Guarda los valores efectivos (incluye los de omisión)
            const values = {};
            for (const flt of data.filters) {
                values[flt.id] = flt.value;
            }
            this.state.filterValues = values;
        } finally {
            this.state.loading = false;
        }
    }

    // ---------------- Filtros ----------------
    setFilter(filter, value) {
        this.state.filterValues = { ...this.state.filterValues, [filter.id]: value };
        this.reload();
    }

    setPeriod(filter, preset) {
        const current = this.state.filterValues[filter.id] || {};
        this.setFilter(filter, { ...current, preset });
    }

    setPeriodDate(filter, key, ev) {
        const current = this.state.filterValues[filter.id] || {};
        this.setFilter(filter, { ...current, preset: "custom", [key]: ev.target.value || false });
    }

    toggleSelection(filter, value) {
        const current = new Set(this.state.filterValues[filter.id] || []);
        current.has(value) ? current.delete(value) : current.add(value);
        this.setFilter(filter, [...current]);
    }

    onTextFilter(filter, ev) {
        if (ev.key === "Enter" || ev.type === "change") {
            this.setFilter(filter, ev.target.value);
        }
    }

    clearFilters() {
        this.state.filterValues = {};
        this.reload();
    }

    // ---------------- Detalle ----------------
    async drilldown(widget, { group_key = null, measure_id = null, group2_key = null } = {}) {
        const action = await this.orm.call("business.dashboard.widget", "get_drilldown_action", [[widget.id]], {
            filter_values: this.state.filterValues, group_key, measure_id, group2_key,
        });
        this.action.doAction(action);
    }

    async openRecord(widget, record) {
        const action = await this.orm.call("business.dashboard.widget", "get_record_action", [[widget.id], record.id]);
        this.action.doAction(action);
    }

    // ---------------- Configuración ----------------
    editWidget(widget) {
        this.dialog.add(FormViewDialog, {
            resModel: "business.dashboard.widget",
            resId: widget.id,
            title: _t("Configurar elemento"),
            onRecordSaved: () => this.reload(),
        });
    }

    addWidget() {
        this.dialog.add(FormViewDialog, {
            resModel: "business.dashboard.widget",
            title: _t("Nuevo elemento"),
            context: { default_dashboard_id: this.state.activeId },
            onRecordSaved: () => this.reload(),
        });
    }

    configureDashboard() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "business.dashboard",
            res_id: this.state.activeId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ---------------- Ayudas para la plantilla ----------------
    get currency() {
        return this.state.data?.currency || { symbol: "$", position: "before" };
    }

    kpiText(widget) {
        return formatValue(widget.value, widget.format, { abbreviate: widget.abbreviate, currency: this.currency });
    }

    kpiFull(widget) {
        return formatValue(widget.value, widget.format, { currency: this.currency });
    }

    listCell(column, value) {
        if (["float", "monetary", "integer"].includes(column.type) && value !== "") {
            return formatValue(value, column.type === "monetary" ? "monetary" : column.type === "integer" ? "integer" : "number",
                { currency: this.currency });
        }
        return value;
    }

    widgetClass(widget) {
        return `o_bd_widget o_bd_${widget.type} o_bd_col_${widget.width}`;
    }
}

registry.category("actions").add("business_dashboard", BusinessDashboardAction);
