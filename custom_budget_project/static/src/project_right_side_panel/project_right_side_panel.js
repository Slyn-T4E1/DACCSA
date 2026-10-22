import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ProjectRightSidePanel } from "@project/components/project_right_side_panel/project_right_side_panel";

/**
 * Sección adicional "Presupuestos por posición presupuestaria" (base_account_budget),
 * independiente de la sección nativa "Presupuestos" de Odoo 19.
 */
patch(ProjectRightSidePanel.prototype, {
    async loadPositionBudgets() {
        const items = await this.orm.call(
            "project.project",
            "get_position_budget_items",
            [[this.projectId]],
            { context: this.context },
        );
        this.state.data.position_budget_items = items;
        return items;
    },

    addPositionBudget() {
        const items = this.state.data.position_budget_items;
        this.dialog.add(FormViewDialog, {
            context: {
                ...this.context,
                position_budget_from_project: true,
                default_project_id: this.projectId,
                default_company_id: items.company_id,
            },
            title: _t("Nuevo presupuesto por posición presupuestaria"),
            resModel: "budget.budget",
            onRecordSaved: async () => {
                await this.loadPositionBudgets();
            },
            viewId: items.form_view_id,
        });
    },

    get panelVisible() {
        return super.panelVisible || this.state.data.show_position_budget_items;
    },
});
