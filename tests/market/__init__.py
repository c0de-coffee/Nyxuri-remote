"""Market layer tests (T2): data/actions are pure; screens run headless.

`tests/market/support.stage` mirrors the kernel tests' `_stage` helper —
fake unit trees inside TempEnv, never the real ~/.config.
"""

from pathlib import Path


def stage(ctx, spec):
    """Create unit dirs under a temp units_src and point the env at it.

    spec maps unit id -> {"manifest": toml text | None, "files": {rel: content}}.
    """
    configs = ctx.home / "configs-src"
    configs.mkdir(exist_ok=True)
    for uid, entry in spec.items():
        unit = configs / uid
        unit.mkdir(exist_ok=True)
        if entry.get("manifest") is not None:
            (unit / "manifest.toml").write_text(entry["manifest"], encoding="utf-8")
        for rel, content in entry.get("files", {}).items():
            p = unit / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    ctx.env.units_src = configs
