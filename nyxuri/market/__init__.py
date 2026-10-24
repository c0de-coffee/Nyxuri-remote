"""Market — Nyxuri's interactive face (the only Textual layer in the tree).

Public entry: :func:`nyxuri.market.run` (see ``gate.run``). Importing this
package never imports Textual; the App is loaded lazily once the gate has
confirmed the dependency, so every CLI verb works without it.
"""

from nyxuri.market.gate import run  # noqa: F401  (re-exported entry)

__all__ = ["run"]
