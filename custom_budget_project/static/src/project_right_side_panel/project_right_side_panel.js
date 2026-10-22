import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ProjectRightSidePanel } from "@project/components/project_right_side_panel/project_right_side_panel";

/**
 * El botón "Agregar presupuesto" abre el presupuesto de base_account_budget
 * (budget.budget) en lugar del presupuesto analítico nativo, como en Odoo 17.
 */
patch(ProjectRightSidePanel.prototype, {
    addBudget() {
        const budgetItems = this.state.data.budget_items;
        if (!budgetItems || budgetItems.budget_model !== "budget.budget") {
            return super.addBudget(...arguments);
        }
        this.dialog.add(FormViewDialog, {
            context: {
                ...this.context,
                project_update: true,
                default_project_id: this.projectId,
                default_company_id: budgetItems.company_id,
            },
            title: _t("Nuevo presupuesto"),
            resModel: "budget.budget",
            onRecordSaved: async () => {
                await this.loadBudgets();
            },
            viewId: budgetItems.form_view_id,
        });
    },
});
