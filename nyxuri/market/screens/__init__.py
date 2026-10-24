"""Market screens — the only layer allowed to touch widgets.

Import order matters: this package (and app.py) import Textual, so they are
only ever loaded after the gate confirmed Textual is installed. data.py and
actions.py must stay importable without it.
"""
