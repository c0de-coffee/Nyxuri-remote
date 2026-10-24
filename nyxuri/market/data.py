"""Read-only projections for the market App — its only data layer.

Contract (T2): this module never imports Textual. Screens mount, read a
projection, act through :mod:`nyxuri.market.actions`, then invalidate the
cache so the next read reflects the ledger — the UnitWorkshop ``_audit``
semantics promoted to a protocol shared by every screen.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from nyxuri.kernel import ledger, registry, transaction

# Cache scopes. ``invalidate()`` with no arguments drops everything.
SCOPE_LEDGER = "ledger"
SCOPE_AUDIT = "audit"
SCOPE_PRESETS = "presets"


@dataclass
class UnitDetail:
    """One unit's manifest declarations joined with its ledger record."""

    uid: str
    state: str = "-"
    preset: str = "-"
    label: str = ""
    category: str = ""
    packages: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    privilege: str = ""
    audit: str = ""
    vault: str = ""
    known: bool = False  # a manifest exists in the registry


class MarketData:
    """Projection + invalidation cache owned by the App instance."""

    def __init__(self) -> None:
        self._audit: Dict[str, str] = {}
        self._clean = None

    # -- workshop ------------------------------------------------------

    def unit_rows(self) -> List[Dict[str, str]]:
        """Ledger rows: one per known unit or ledger record, id-sorted."""
        recs = ledger.all_units()
        ids = sorted(set(registry.unit_ids()) | set(recs))
        return [
            {"uid": uid, "state": (recs.get(uid) or {}).get("state") or "-",
             "preset": (recs.get(uid) or {}).get("preset") or "-"}
            for uid in ids
        ]

    def unit_detail(self, uid: str) -> UnitDetail:
        rec = ledger.get_unit(uid) or {}
        detail = UnitDetail(
            uid=uid,
            state=rec.get("state") or "-",
            preset=rec.get("preset") or "-",
            vault=rec.get("vault") or "",
            known=uid in registry.unit_ids(),
        )
        if detail.known:
            m = registry.load_unit(uid)
            detail.label = m.label or ""
            detail.category = m.category or ""
            detail.packages = [*m.packages_repo, *m.packages_aur, *m.packages_flatpak]
            detail.dependencies = list(m.dependencies)
            if m.requires_root or m.system_paths:
                detail.privilege = ", ".join(m.system_paths) or "root"
        detail.audit = self.audit_for(uid)
        return detail

    def audit_for(self, uid: str) -> str:
        """Lazy three-state reconciliation for one unit (cached)."""
        if uid not in self._audit:
            try:
                self._audit.update(transaction.audit_units(uid))
            except Exception:
                self._audit[uid] = ""
        return self._audit.get(uid, "")

    def audit_report(self) -> Dict[str, str]:
        """Full three-state report (Synced / Drifted / Ghost)."""
        try:
            return transaction.audit_units()
        except Exception:
            return {}

    def enabled_units(self) -> List[str]:
        return [uid for uid, rec in ledger.all_units().items()
                if rec.get("state") == "enabled"]

    # -- presets ----------------------------------------------------------

    def apps(self) -> List[str]:
        """Deployable apps (the left pane of the presets studio)."""
        from nyxuri.deploy import discover_config_items

        return discover_config_items()

    def presets_for(self, app: str) -> List[Dict[str, str]]:
        """(name, source, is_active) rows, default first (cached per app)."""
        cache = self.__dict__.setdefault("_presets", {})
        if app not in cache:
            from nyxuri.desktop.presets import collect_presets

            cache[app] = [
                {"name": name, "source": source, "active": str(is_active).lower()}
                for name, source, is_active in collect_presets(app)
            ]
        return cache[app]

    def active_preset(self, app: str) -> str:
        for row in self.presets_for(app):
            if row["active"] == "true":
                return row["name"]
        return "default"

    def preset_info(self, app: str, name: str):
        """desktop.presets.PresetInfo projection (read-only)."""
        from nyxuri.desktop.presets import get_preset_info

        return get_preset_info(app, name)

    def parts_for(self, app: str) -> Dict[str, Dict]:
        """Part slots: slot → {target, desc, variants, default}."""
        from nyxuri.deploy.preset import list_parts

        return list_parts(app)

    def active_part(self, app: str, slot: str) -> str:
        from nyxuri.deploy.preset import get_active_part

        return get_active_part(app, slot)

    # -- install components -------------------------------------------------

    def component_options(self, mode: str = "full") -> Dict:
        """The master component checklist as data (was run_master_component_menu).

        WM rows are a radio group (preferred WM pre-selected); app rows are
        checkboxes (optional apps pre-checked only when installed); heavy
        assets appear for full installs; backup rides as a behavior toggle.
        """
        import os

        from nyxuri.core import SUPPORTED_WMS, detect_preferred_wm
        from nyxuri.deploy import discover_config_items, discover_manifest_apps, discover_optional_apps
        from nyxuri.deploy.deploy import wallpapers_pack_present
        from nyxuri.pkg.deps import is_dep_installed

        items = discover_config_items()
        wm_items = [i for i in items if i in SUPPORTED_WMS]
        app_items = [i for i in items if i not in SUPPORTED_WMS]
        preferred_wm = detect_preferred_wm()
        desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

        wms = []
        for wm in wm_items:
            running = (wm in desktop_env or desktop_env in wm) if desktop_env else False
            wms.append({
                "name": wm,
                "selected": wm == preferred_wm,
                "running": running,
                "installed": is_dep_installed(wm),
            })

        optional_set = set(discover_optional_apps())
        manifests = dict(discover_manifest_apps())
        apps = []
        for item in app_items:
            installed = True
            if item in optional_set:
                m = manifests.get(item)
                if m is not None:
                    installed = is_dep_installed(m.detect)
            apps.append({"name": item, "installed": installed,
                         "optional": item in optional_set, "selected": installed})

        return {
            "wms": wms,
            "apps": apps,
            "wallpapers_present": wallpapers_pack_present(),
            # full installs offer the heavy asset pack
            "wallpapers": mode == "full",
        }

    # -- deps ---------------------------------------------------------------

    def core_deps(self) -> List[Dict]:
        """Core dependency rows with installed verdicts."""
        from nyxuri.pkg.deps import check_all_deps

        status = check_all_deps()
        return [{"name": dep, "installed": installed} for dep, installed in status.items()]

    def supply_apps(self) -> List[Dict]:
        """Catalog + optional-unit rows with category and installed verdict."""
        from nyxuri.pkg.deps import supply_status

        return supply_status()

    # -- snapshots ------------------------------------------------------------

    def snapshots(self) -> List[Dict]:
        """Snapshot rows (index 1-based, name, note) newest-last, as listed."""
        from nyxuri.state.backup import _read_snapshot_note, get_all_backups

        backups = get_all_backups()
        return [
            {"index": i, "name": b.name, "note": _read_snapshot_note(b)}
            for i, b in enumerate(backups, start=1)
        ]

    # -- uninstall --------------------------------------------------------

    def uninstall_options(self) -> List[Dict]:
        """Scope rows (group headers + items) — delegates to state.uninstall."""
        from nyxuri.state.uninstall import uninstall_options

        return uninstall_options()

    # -- clean --------------------------------------------------------------

    def clean_tasks(self):
        """(tasks, sizes, flat_roots) — one du walk per call, cached."""
        if self._clean is None:
            from nyxuri.desktop.clean import discover_clean_tasks

            self._clean = discover_clean_tasks()
        return self._clean

    # -- cache protocol --------------------------------------------------

    def invalidate(self, *scopes: str) -> None:
        """Drop cached projections; no arguments drops everything."""
        if not scopes or SCOPE_AUDIT in scopes:
            self._audit.clear()
        if not scopes or SCOPE_PRESETS in scopes:
            self.__dict__.get("_presets", {}).clear()
        if not scopes:
            self._clean = None
        # ledger rows are cheap (a state.json read) — always re-read.
