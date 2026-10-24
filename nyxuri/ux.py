"""Zero-dependency terminal UX base shared by the CLI and the market App.

The engine core (kernel / deploy / pkg / state / desktop) may import this
module freely: it is pure standard library, exactly like the rest of the
engine. The only declared third-party dependency in the tree is Textual, and
it lives behind `nyxuri/market/` — never here.

Contents (deliberately small):
  - prompt_confirm / press_any_key   single-key line-form prompts
  - format_steps                     transaction Step → bilingual prose lines
  - display_width / pad_display / truncate_display    CJK-aware column math
  - show_logo / write_cleared        line-form brand header
  - select_many                      numbered line-form multi-select (CLI only)
  - drain_stdin                      discard pending cooked-mode input
"""

import atexit
import os
import re
import select
import shutil
import sys
import termios
import tty
import unicodedata
from typing import Any, List, Optional

from nyxuri.core import Colors
from nyxuri.core import Environment, get_env
from nyxuri.core import msg, get_env_var

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def stdin_fd() -> Optional[int]:
    """Return the stdin fd when it is a real terminal, else None."""
    try:
        if not sys.stdin.isatty():
            return None
        return sys.stdin.fileno()
    except (AttributeError, ValueError, OSError):
        return None


class _TerminalGuard:
    """Fail-safe: a crashed prompt must never leave the terminal raw/cursorless."""

    _orig: Optional[List[Any]] = None

    @classmethod
    def capture(cls, fd: int) -> None:
        try:
            cls._orig = termios.tcgetattr(fd)
        except Exception:
            cls._orig = None

    @classmethod
    def restore(cls) -> None:
        """Never raise: this also runs from atexit, where stdin may be gone."""
        if cls._orig is not None:
            try:
                if sys.stdin.isatty():
                    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, cls._orig)
            except Exception:
                pass
            cls._orig = None
        try:
            if sys.stdout.isatty():
                sys.stdout.write(Colors.CURSOR_SHOW)
                sys.stdout.flush()
        except Exception:
            pass


atexit.register(_TerminalGuard.restore)


# --- Geometric Column Alignment (CJK = 2 columns) ---------------------------

def _char_width(ch: str) -> int:
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Cf", "Mn", "Me"):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def display_width(text: str) -> int:
    """Real physical terminal column width of a string (CJK = 2 cols)."""
    clean_text = ANSI_ESCAPE_RE.sub("", text)
    return sum(_char_width(ch) for ch in clean_text)


def pad_display(text: str, width: int) -> str:
    """Pad with trailing spaces to an exact visual column width."""
    curr = display_width(text)
    if curr < width:
        return text + (" " * (width - curr))
    return text


def truncate_display(text: str, width: int, suffix: str = "…") -> str:
    """Clip ANSI-styled text to a physical width without splitting CJK glyphs."""
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text

    suffix_width = display_width(suffix)
    if suffix_width > width:
        return truncate_display(suffix, width, suffix="")
    content_width = width - suffix_width
    output: List[str] = []
    used = 0
    pos = 0
    while pos < len(text):
        match = ANSI_ESCAPE_RE.match(text, pos)
        if match:
            output.append(match.group(0))
            pos = match.end()
            continue
        char = text[pos]
        char_width = _char_width(char)
        if used + char_width > content_width:
            break
        output.append(char)
        used += char_width
        pos += 1
    reset = Colors.RESET if ANSI_ESCAPE_RE.search(text) else ""
    return "".join(output) + suffix + reset


# --- Single-key raw reads ---------------------------------------------------

def _drain_fd(fd: Optional[int]) -> None:
    """Discard input already queued (stale Enter, auto-repeat tail)."""
    if fd is None:
        return
    while True:
        ready, _, _ = select.select([fd], [], [], 0)
        if not ready:
            return
        try:
            if os.read(fd, 64) == b"":
                return
        except OSError:
            return


class _RawKeys:
    """Context manager: echo-off raw mode for one prompt read.

    No-op when stdin is not a real tty — tests patch stdin and the cooked
    reader path, exactly as before.
    """

    def __init__(self) -> None:
        self.fd = stdin_fd()
        self.old = None

    def __enter__(self) -> "_RawKeys":
        if self.fd is not None:
            try:
                self.old = termios.tcgetattr(self.fd)
                _TerminalGuard.capture(self.fd)
                tty.setraw(self.fd)
            except Exception:
                self.old = None
        _drain_fd(self.fd)
        return self

    def __exit__(self, *exc: Any) -> None:
        _drain_fd(self.fd)
        if self.old is not None and self.fd is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
            except Exception:
                pass
        return None

    def read(self) -> str:
        if self.fd is None:
            return "ENTER"
        try:
            data = os.read(self.fd, 1)
        except OSError:
            return "EOF"
        if not data:
            return "EOF"
        if data in (b"\r", b"\n"):
            return "ENTER"
        if data == b"\x1b":
            return "ESC"
        if data in (b"\x03", b"\x04"):
            return "EXIT"
        if data == b" ":
            return "SPACE"
        return data.decode("utf-8", "ignore")


def prompt_confirm(prompt_key: str, default: str = "y", destructive: bool = False) -> bool:
    """Bilingual single-key confirmation (True = Yes).

    Destructive prompts always ask, even under NYXURI_AUTO_YES: express mode
    speeds things up, it must not consent to data loss on the user's behalf.
    """
    if get_env_var("AUTO_YES", "0") == "1" and not destructive:
        return True

    sys.stdout.write(msg(prompt_key))
    sys.stdout.flush()
    if stdin_fd() is None:
        return default.lower().startswith("y")

    with _RawKeys() as raw:
        key = raw.read()
    sys.stdout.write("\n")
    sys.stdout.flush()
    return _resolve_confirm(key, default)


def _resolve_confirm(key: str, default: str) -> bool:
    if key in ("y", "Y"):
        return True
    if key == "ENTER":
        return default.lower().startswith("y")
    return False


def _read_key_once() -> str:
    """Read one key in raw mode, then restore cooked mode."""
    if stdin_fd() is None:
        return "ENTER"
    with _RawKeys() as raw:
        return raw.read()


def press_any_key() -> None:
    """Prompt to press any key to continue (line form, no full-screen)."""
    if stdin_fd() is not None:
        sys.stdout.write(msg("press_any_key"))
        sys.stdout.flush()
        _read_key_once()
        sys.stdout.write("\n")
        sys.stdout.flush()


def drain_stdin() -> None:
    """Discard leftover cooked-mode input (before a child reads /dev/tty)."""
    _drain_fd(stdin_fd())


# --- Rendering primitives ---------------------------------------------------

def clear_screen() -> None:
    """Clear the visible terminal without destroying scrollback history."""
    if sys.stdin.isatty():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def write_cleared(text: str) -> None:
    """Write text, wiping right-side ghost chars on every line."""
    if not text:
        return
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i == len(lines) - 1:
            sys.stdout.write(line)
        else:
            sys.stdout.write(f"{line}\033[K\n")


def show_logo(env: Optional[Environment] = None) -> int:
    """Render the Nyxuri ASCII brand header; returns rows written."""
    if env is None:
        env = get_env()

    terminal = shutil.get_terminal_size((80, 24))
    if terminal.columns < 66 or terminal.lines < 20:
        mode_line = truncate_display(f"Mode: {env.mode_label} ({env.repo_dir})", max(12, terminal.columns - 4))
        logo = (
            f"{Colors.BOLD_PURPLE}\n  NYXURI{Colors.RESET}  "
            f"{Colors.BOLD_WHITE}{env.version}{Colors.RESET}\n"
            f"  {Colors.DARK_GRAY}{mode_line}{Colors.RESET}\n\n"
        )
        write_cleared(logo)
        return logo.count("\n")

    mode_line = truncate_display(
        f"Mode: {env.mode_label} ({env.repo_dir})",
        max(12, terminal.columns - 4),
    )
    logo = (
        f"{Colors.BOLD_PURPLE}\n"
        " ███╗   ██╗██╗   ██╗██╗  ██╗    ██╗   ██╗██████╗ ██╗\n"
        " ████╗  ██║╚██╗ ██╔╝╚██╗██╔╝    ██║   ██║██╔══██╗██║\n"
        " ██╔██╗ ██║ ╚████╔╝  ╚███╔╝     ██║   ██║██████╔╝██║\n"
        " ██║╚██╗██║  ╚██╔╝   ██╔██╗     ██║   ██║██╔══██╗██║\n"
        " ██║ ╚████║   ██║   ██╔╝ ██╗    ╚██████╔╝██║  ██║██║\n"
        " ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝     ╚═════╝ ╚═╝  ╚═╝╚═╝\n"
        f"{Colors.RESET}\n"
        f"  {Colors.BOLD_CYAN}Nyxuri Desktop Environment Setup{Colors.RESET} {Colors.DARK_GRAY}|{Colors.RESET} {Colors.BOLD_WHITE}{env.version}{Colors.RESET}\n"
        f"  {Colors.DARK_GRAY}{mode_line}{Colors.RESET}\n\n"
    )
    write_cleared(logo)
    return logo.count("\n")


# --- Transaction step prose (shared by CLI verbs and the App) ---------------

def format_steps(steps) -> List[str]:
    """Transaction Steps → bilingual prose lines."""
    out: List[str] = []
    for step in steps:
        head, *extra = step.detail.split("; ")
        color, mark = Colors.BOLD_GREEN, "[✓]"
        key = ""
        arg = ""
        if head == "enabled":
            key = "cli_step_enabled"
        elif head == "already-enabled":
            key, color, mark = "cli_step_already_enabled", Colors.DIM, "[•]"
        elif head == "disabled":
            key = "cli_step_disabled"
        elif head == "already-disabled":
            key, color, mark = "cli_step_already_disabled", Colors.DIM, "[•]"
        elif head == "deploy-failed":
            key, color, mark = "cli_step_deploy_failed", Colors.BOLD_RED, "[✗]"
        elif head.startswith("missing-packages: "):
            key, arg = "cli_step_missing_packages", head.split(": ", 1)[1]
        elif head.startswith("blocked-by-enabled-dependents: "):
            key, arg = "cli_step_blocked", head.split(": ", 1)[1]
        else:
            key, color, mark = "cli_step_failed", Colors.BOLD_RED, "[✗]"
        notes = []
        for part in extra:
            if part.startswith("archived: "):
                notes.append(msg("cli_step_archived", part.split(": ", 1)[1]))
            elif part.startswith("foreign-left: "):
                notes.append(msg("cli_step_foreign", part.split(": ", 1)[1]))
            elif part.startswith("packages-left: "):
                notes.append(msg("cli_step_packages_left", part.split(": ", 1)[1]))
        line = msg(key, step.unit, arg) if arg else msg(key, step.unit)
        if notes:
            line += " (" + "; ".join(notes) + ")"
        out.append(f"{color}{mark}{Colors.RESET} {line}")
    return out


# --- Line-form selection (CLI only; the App has real screens) ---------------

def select_many(labels: List[str]) -> Optional[List[int]]:
    """Numbered multi-select over a cooked-mode line read.

    Returns 0-based indices, or None when the user cancels (empty / EOF /
    invalid input). Accepts ``1 3 5``, ``1,3,5``, ranges ``2-4`` and ``all``.
    """
    for idx, label in enumerate(labels, start=1):
        sys.stdout.write(f"  {Colors.BOLD_CYAN}[{idx}]{Colors.RESET} {label}\n")
    sys.stdout.write(msg("cli_select_prompt"))
    sys.stdout.flush()
    try:
        line = sys.stdin.readline()
    except (OSError, KeyboardInterrupt):
        return None
    if not line.strip():
        return None
    picks: List[int] = []
    for token in re.split(r"[\s,]+", line.strip().lower()):
        if not token:
            continue
        if token in ("all", "*"):
            return list(range(len(labels)))
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", token)
        if not match:
            print(msg("cli_select_invalid"), file=sys.stderr)
            return None
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if not (1 <= start <= end <= len(labels)):
            print(msg("cli_select_invalid"), file=sys.stderr)
            return None
        picks.extend(range(start - 1, end))
    return sorted(set(picks)) or None
