from __future__ import annotations

import os
import shutil
import textwrap


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def color(text: str, fg: int | None = None, bg: int | None = None, style: str = "") -> str:
    parts: list[str] = []
    if style:
        parts.append(style)
    if fg is not None:
        parts.append(f"\033[38;5;{fg}m")
    if bg is not None:
        parts.append(f"\033[48;5;{bg}m")
    return "".join(parts) + text + RESET


def terminal_width(default: int = 96) -> int:
    if "COLUMNS" in os.environ and os.environ["COLUMNS"].isdigit():
        return max(64, int(os.environ["COLUMNS"]))
    return max(64, shutil.get_terminal_size((default, 24)).columns)


def gradient_header(title: str, subtitle: str, width: int) -> str:
    colors = [39, 45, 51, 50, 49, 48, 47]
    inner = width - 2
    title_line = title.center(inner)
    sub_line = subtitle.center(inner)
    lines = [title_line, sub_line]
    rendered: list[str] = []
    for line in lines:
        out = []
        for idx, ch in enumerate(line):
            out.append(color(ch, fg=colors[idx % len(colors)], style=BOLD))
        rendered.append("".join(out))
    top = color("+" + "-" * (width - 2) + "+", fg=27, style=BOLD)
    mid_a = color("|", fg=27, style=BOLD) + rendered[0] + color("|", fg=27, style=BOLD)
    mid_b = color("|", fg=27, style=BOLD) + rendered[1] + color("|", fg=27, style=BOLD)
    bottom = color("+" + "-" * (width - 2) + "+", fg=27, style=BOLD)
    return "\n".join([top, mid_a, mid_b, bottom])


def panel(title: str, body: str, width: int, border: int, accent: int) -> str:
    inner = width - 4
    wrapped = textwrap.wrap(body, width=inner) or [""]
    header = color(f"  {title}  ", fg=accent, style=BOLD)
    top = color("+" + "-" * (width - 2) + "+", fg=border)
    lines = [top, color("| ", fg=border) + header.ljust(inner) + color(" |", fg=border)]
    for line in wrapped:
        lines.append(color("| ", fg=border) + color(line.ljust(inner), fg=252) + color(" |", fg=border))
    lines.append(top)
    return "\n".join(lines)


def render_dashboard() -> str:
    width = min(terminal_width(), 110)
    card_width = width if width < 90 else (width - 3) // 2
    spacer = "\n" if width < 90 else "   "

    hero = gradient_header("FARDANA CONTENTS", "Refreshed visual style", width)

    left = panel(
        "Status",
        "Design refresh active. Layout now uses a branded hero, clear hierarchy, and high-contrast sections.",
        card_width,
        border=31,
        accent=81,
    )
    right = panel(
        "Next Steps",
        "Connect this shell UI to MCP actions and stream responses into these styled sections for a consistent experience.",
        card_width,
        border=24,
        accent=49,
    )

    if width < 90:
        cards = left + "\n" + right
    else:
        left_lines = left.splitlines()
        right_lines = right.splitlines()
        rows = max(len(left_lines), len(right_lines))
        left_lines += [" " * card_width] * (rows - len(left_lines))
        right_lines += [" " * card_width] * (rows - len(right_lines))
        cards = "\n".join(l + spacer + r for l, r in zip(left_lines, right_lines))

    footer = color("Press Ctrl+C to exit.", fg=244, style=DIM)
    return "\n\n".join([hero, cards, footer])


def main() -> None:
    print(render_dashboard())


if __name__ == "__main__":
    main()
