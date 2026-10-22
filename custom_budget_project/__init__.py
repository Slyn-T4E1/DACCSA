import logging

from . import models
from .data.legacy_budget_post_accounts import BUDGET_POST_ACCOUNTS

_logger = logging.getLogger(__name__)


def restore_budget_post_accounts(env, rows=BUDGET_POST_ACCOUNTS):
    """Restaura la relación posición presupuestaria → cuentas contables de v16.

    Solo inserta cuando la posición y la cuenta existen con el mismo id y el mismo
    nombre / código que en v16. Es idempotente.
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
            "custom_budget_project: %s relaciones posición-cuenta de v16 omitidas "
            "(posición o cuenta no encontrada con el mismo id/nombre/código). Primeras: %s",
            len(skipped), skipped[:10],
        )
    _logger.info(
        "custom_budget_project: %s relaciones posición-cuenta restauradas (%s ya existían).",
        inserted, len(to_insert) - inserted,
    )
    env["account.budget.post"].invalidate_model(["account_ids"])
    return {"inserted": inserted, "existing": len(to_insert) - inserted, "skipped": skipped}


def post_init_hook(env):
    restore_budget_post_accounts(env)
