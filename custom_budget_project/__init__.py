import logging

from odoo import Command

from . import models
from .data.legacy_budget_post_accounts import BUDGET_POST_ACCOUNTS
from .data.legacy_budgets import LEGACY_BUDGET_LINES, LEGACY_BUDGETS

_logger = logging.getLogger(__name__)


def restore_budget_post_accounts(env, rows=BUDGET_POST_ACCOUNTS):
    """Restaura la relación posición presupuestaria → cuentas contables de DACSA (v17).

    Solo inserta cuando la posición y la cuenta existen con el mismo id y el mismo
    nombre / código que en v17. Es idempotente.
    """
    posts = {
        post.id: post.name
        for post in env["account.budget.post"].sudo().with_context(active_test=False).search([])
    }
    accounts = {
        account.id: account.code
        for account in env["account.account"].sudo().with_context(active_test=False).browse(
            {row[2] for row in rows}
        ).exists()
    }
    to_insert = []
    skipped = []
    for post_id, post_name, account_id, account_code in rows:
        if posts.get(post_id) == post_name and accounts.get(account_id) == account_code:
            to_insert.append((post_id, account_id))
        else:
            skipped.append((post_id, post_name, account_id, account_code))

    inserted = 0
    for post_id, account_id in to_insert:
        env.cr.execute(
            """
            INSERT INTO account_budget_rel (budget_id, account_id)
            SELECT %s, %s
             WHERE NOT EXISTS (
                   SELECT 1 FROM account_budget_rel
                    WHERE budget_id = %s AND account_id = %s)
            """,
            (post_id, account_id, post_id, account_id),
        )
        inserted += env.cr.rowcount
    if skipped:
        _logger.warning(
            "custom_budget_project: %s relaciones posición-cuenta de v17 omitidas "
            "(posición o cuenta no encontrada con el mismo id/nombre/código). Primeras: %s",
            len(skipped), skipped[:10],
        )
    _logger.info(
        "custom_budget_project: %s relaciones posición-cuenta restauradas (%s ya existían).",
        inserted, len(to_insert) - inserted,
    )
    env["account.budget.post"].invalidate_model(["account_ids"])
    return {"inserted": inserted, "existing": len(to_insert) - inserted, "skipped": skipped}


LEGACY_XMLID_PREFIX = "legacy_budget_v17_"
LEGACY_MIN_POSITION_MATCH = 0.9


def restore_legacy_budgets(env, budgets=LEGACY_BUDGETS, lines=LEGACY_BUDGET_LINES):
    """Recrea en budget.budget / budget.lines los presupuestos de DACSA en Odoo 17.

    * Idempotente: cada presupuesto creado queda marcado con el xmlid
      custom_budget_project.legacy_budget_v17_<id v17> (noupdate) y no se vuelve a crear.
      Si ya existe un presupuesto con el mismo id y nombre sin xmlid (por ejemplo, el
      que se cargó manualmente en pruebas), se adopta en lugar de duplicarlo.
    * Solo usa posiciones presupuestarias que coinciden en id y nombre con v17 y cuentas
      analíticas que coinciden en id y nombre (es_MX o en_US). Si menos del 90 % de las
      posiciones coinciden, la base no corresponde a DACSA y no se importa nada.
    * Conserva el estado de v17 (borrador, confirmado o cancelado).
    """
    env = env(context=dict(env.context, tracking_disable=True, mail_create_nolog=True,
                           mail_notrack=True, active_test=False))
    Budget = env["budget.budget"].sudo()
    Data = env["ir.model.data"].sudo()

    position_ids = {line[5] for line in lines if line[5]}
    positions = {post.id: post.name for post in env["account.budget.post"].sudo().browse(position_ids).exists()}
    expected = {line[5]: line[6] for line in lines if line[5]}
    matched = sum(1 for pid, name in expected.items() if positions.get(pid) == name)
    if expected and matched / len(expected) < LEGACY_MIN_POSITION_MATCH:
        _logger.warning(
            "custom_budget_project: presupuestos v17 no importados; solo %s de %s posiciones "
            "presupuestarias coinciden en id/nombre (la base no corresponde a DACSA).",
            matched, len(expected),
        )
        return {"created": 0, "adopted": 0, "existing": 0, "skipped_lines": [], "aborted": True}

    analytic_ids = {line[2] for line in lines if line[2]}
    analytic_es = {a.id: a.name for a in env["account.analytic.account"].sudo().with_context(lang="es_MX").browse(analytic_ids).exists()}
    analytic_en = {a.id: a.name for a in env["account.analytic.account"].sudo().with_context(lang="en_US").browse(analytic_ids).exists()}
    user_ids = set(env["res.users"].sudo().browse({b[5] for b in budgets if b[5]}).exists().ids)
    company = env["res.company"].sudo().browse(1).exists() or env.company

    lines_by_budget = {}
    for line in lines:
        lines_by_budget.setdefault(line[1], []).append(line)

    existing_xmlids = {
        data.name: data.res_id
        for data in Data.search([
            ("module", "=", "custom_budget_project"),
            ("model", "=", "budget.budget"),
            ("name", "=like", LEGACY_XMLID_PREFIX + "%"),
        ])
    }
    created = adopted = existing = 0
    skipped_lines = []
    for budget_id, name, state, date_from, date_to, user_id in budgets:
        xmlid = f"{LEGACY_XMLID_PREFIX}{budget_id}"
        if xmlid in existing_xmlids:
            if Budget.browse(existing_xmlids[xmlid]).exists():
                existing += 1
                continue
            # El presupuesto marcado se eliminó: se limpia el xmlid y se vuelve a crear.
            Data.search([("module", "=", "custom_budget_project"), ("name", "=", xmlid)]).unlink()
        same = Budget.browse(budget_id).exists()
        if same and same.name == name and not same.get_external_id().get(same.id):
            record = same
            adopted += 1
        else:
            line_vals = []
            for (line_id, _bid, analytic_id, analytic_name_es, analytic_name_en, position_id,
                 position_name, l_from, l_to, paid_date, planned) in lines_by_budget.get(budget_id, []):
                analytic_ok = analytic_id and (
                    analytic_es.get(analytic_id) == analytic_name_es
                    or analytic_en.get(analytic_id) == analytic_name_en
                )
                position_ok = position_id and positions.get(position_id) == position_name
                if not analytic_ok and not position_ok:
                    skipped_lines.append(line_id)
                    continue
                line_vals.append(Command.create({
                    "analytic_account_id": analytic_id if analytic_ok else False,
                    "general_budget_id": position_id if position_ok else False,
                    "date_from": l_from,
                    "date_to": l_to,
                    "paid_date": paid_date or False,
                    "planned_amount": planned,
                }))
            record = Budget.create({
                "name": name,
                "date_from": date_from,
                "date_to": date_to,
                "creating_user_id": user_id if user_id in user_ids else False,
                "company_id": company.id,
                "budget_line": line_vals,
            })
            if state == "confirm":
                record.action_budget_confirm()
            elif state == "cancel":
                record.action_budget_cancel()
            created += 1
        Data.create({
            "module": "custom_budget_project",
            "name": xmlid,
            "model": "budget.budget",
            "res_id": record.id,
            "noupdate": True,
        })
    if skipped_lines:
        _logger.warning(
            "custom_budget_project: %s líneas de presupuesto v17 omitidas (sin cuenta analítica "
            "ni posición coincidente). Ids v17: %s", len(skipped_lines), skipped_lines[:20],
        )
    _logger.info(
        "custom_budget_project: presupuestos v17 creados %s, adoptados %s, ya existentes %s.",
        created, adopted, existing,
    )
    return {"created": created, "adopted": adopted, "existing": existing,
            "skipped_lines": skipped_lines, "aborted": False}


def post_init_hook(env):
    restore_budget_post_accounts(env)
    restore_legacy_budgets(env)
