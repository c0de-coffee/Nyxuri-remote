"""Market actions — every mutation routes through the engine's own paths.

Contract (T2): no Textual imports here. The suspend decision belongs to the
App (``handoff``); these functions run identically inside a suspended
terminal, in a worker, or under a headless test. Package installation
follows the CLI ``_cmd_on`` order: disclose the plan, disclose missing
packages, then one transaction with the shared installer injected.
"""

import sys
from typing import List, Optional, Tuple

from nyxuri.kernel import ledger, registry, transaction


def _installer(unit_id: str, missing: List[str]) -> bool:
    from nyxuri.pkg.deps import unit_package_installer

    return unit_package_installer(unit_id, missing)


def plan_on_disclosure(uid: str) -> Tuple[List[str], List[str]]:
    """Read-only disclosure: (incoming units, missing packages).

    Mirrors ``nyxuri.cli._cmd_on``: incoming = enabled closure minus the
    already-enabled; missing = declared packages not yet installed.
    """
    plan = transaction.plan_on(uid)
    enabled = {u for u, rec in ledger.all_units().items()
               if rec.get("state") == "enabled"}
    incoming = [u for u in plan if u not in enabled]
    missing: List[str] = []
    for candidate in incoming:
        try:
            missing.extend(transaction.missing_packages(registry.load_unit(candidate)))
        except KeyError:
            continue
    return incoming, missing


def switch_on(uid: str, preset: Optional[str] = None, install: bool = True):
    """Enable through the single transaction path; returns Steps."""
    return transaction.unit_on(
        uid, preset=preset, install_packages=_installer if install else None
    )


def switch_off(uid: str, cascade: bool = False):
    """Disable through the single transaction path; returns Steps."""
    return transaction.unit_off(uid, cascade=cascade)


# --- presets (engine calls identical to nyxuri.preset verbs) -----------------

def apply_preset(app: str, name: str) -> bool:
    from nyxuri.desktop.presets import apply_preset as _apply

    return _apply(app, name)


def apply_part(app: str, slot: str, variant: str) -> bool:
    from nyxuri.deploy.preset import apply_part as _apply

    return _apply(app, slot, variant)


def save_preset(app: str, name: str) -> bool:
    from nyxuri.desktop.presets import save_preset as _save

    return _save(app, name)


def delete_preset(app: str, name: str) -> bool:
    from nyxuri.desktop.presets import delete_preset as _delete

    return _delete(app, name)


def edit_preset(app: str, name: str) -> bool:
    """$EDITOR runs with the terminal handed back (handoff, not in-process)."""
    from nyxuri.desktop.presets import edit_preset as _edit

    return _edit(app, name)


# --- install / update execution halves (workflows) ---------------------------

def install_configs(mode: str, chosen: dict) -> bool:
    """The deploy pipeline behind the components screen (handoff-worthy)."""
    from nyxuri.installer.workflows import install_configs_workflow

    return install_configs_workflow(mode, chosen=chosen)


def update_deploy(chosen: dict) -> bool:
    """The update-grade deploy (carry #139) behind the update screen."""
    from nyxuri.installer.workflows import execute_update_deploy

    return execute_update_deploy(chosen)


def view_update_diff() -> None:
    from nyxuri.installer.workflows import view_update_diff as _diff

    _diff()


def update_pull_and_reexec() -> None:
    """git pull in the handed-off terminal, then execve into fresh code.

    The process image is replaced while the App is suspended (terminal
    already cooked); the fresh process carries the pending-upgrade marker
    and the market flag, so after its deploy offer the App comes back.
    """
    from nyxuri.core import PENDING_UPGRADE_ENV, PENDING_UPGRADE_MENU_ENV, exec_cli, get_env
    from nyxuri.core import msg as _msg
    from nyxuri.pkg.net import safe_git_pull
    from nyxuri.ux import press_any_key

    env = get_env()
    result = safe_git_pull(env.repo_dir)
    if result is True:
        print(_msg("updating_done"))
        press_any_key()
        exec_cli(env, **{PENDING_UPGRADE_ENV: "", PENDING_UPGRADE_MENU_ENV: "1"})
    else:
        print(_msg("updating_failed"), file=sys.stderr)


# --- deps / snapshots / uninstall / clean execution halves -------------------

def install_missing_core(missing: list) -> bool:
    from nyxuri.core import msg as _msg
    from nyxuri.pkg.deps import install_selected_deps

    print(_msg("installing_selected"))
    return bool(install_selected_deps(missing))


def install_apps(chosen: list) -> bool:
    from nyxuri.pkg.deps import install_optional_apps

    return bool(install_optional_apps(chosen))


def snapshot_create(note: str) -> None:
    from nyxuri.state.backup import backup_configs
    from nyxuri.ux import press_any_key

    backup_configs(note=note, interactive=True)
    press_any_key()


def snapshot_delete(index: int) -> bool:
    from nyxuri.state.backup import delete_backup

    return delete_backup(str(index))


def snapshot_rollback(index: int) -> bool:
    from nyxuri.state.backup import rollback_configs

    return rollback_configs(str(index))


def uninstall(selected: set) -> bool:
    from nyxuri.state.uninstall import uninstall_nyxuri

    return uninstall_nyxuri("", selected=selected)


def clean_execute(tasks: list, before: int, sizes, flat_roots) -> int:
    from nyxuri.desktop.clean import execute_clean_tasks

    return execute_clean_tasks(tasks, before=before, sizes=sizes, flat_roots=flat_roots)
