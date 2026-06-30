from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re
import unicodedata
from typing import Iterable


FONT_PATTERNS: dict[str, list[str]] = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01111", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "11110"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
}

ALLOWED_CHARS = set(FONT_PATTERNS) | {" "}
DANGEROUS_CHARS = set("04689ABDOPQR")


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def fmt(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text else "0"


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", without_marks)


def normalize_text(text: str) -> str:
    text = strip_accents(text).upper()
    text = re.sub(r"[^A-Z0-9\- ]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass(slots=True)
class TotemConfig:
    visible_height_mm: float = 200.0
    material_thickness_mm: float = 3.0
    slot_clearance_mm: float = 0.25
    base_width_mm: float = 130.0
    base_depth_mm: float = 50.0
    tab_width_mm: float = 50.0
    tab_height_mm: float = 12.0
    max_name_width_mm: float = 86.0
    max_number_width_mm: float = 68.0
    desired_name_height_mm: float = 17.0
    desired_compound_line_height_mm: float = 12.0
    desired_number_height_mm: float = 55.0
    min_name_height_mm: float = 8.0
    min_number_height_mm: float = 32.0
    min_bridge_mm: float = 0.45
    max_bridge_mm: float = 1.25
    char_gap_units: float = 1.0
    space_units: float = 3.0
    include_base: bool = True
    include_preview: bool = True


@dataclass(slots=True)
class TextLayout:
    lines: list[str]
    line_height_mm: float
    total_height_mm: float
    warnings: list[str]


@dataclass(slots=True)
class GeneratedTotem:
    svg: str
    normalized_name: str
    normalized_number: str
    name_lines: list[str]
    warnings: list[str]


def char_units(ch: str, cfg: TotemConfig) -> float:
    if ch == " ":
        return cfg.space_units
    return 5.0


def text_units(text: str, cfg: TotemConfig) -> float:
    if not text:
        return 0.0
    total = 0.0
    chars = list(text)
    for index, ch in enumerate(chars):
        total += char_units(ch, cfg)
        if index != len(chars) - 1:
            total += cfg.char_gap_units
    return total


def estimate_text_width(text: str, height_mm: float, cfg: TotemConfig) -> float:
    return text_units(text, cfg) * (height_mm / 7.0)


def fit_line_height(
    lines: Iterable[str],
    desired_height_mm: float,
    min_height_mm: float,
    max_width_mm: float,
    cfg: TotemConfig,
) -> tuple[float, list[str]]:
    warnings: list[str] = []
    widest_units = max((text_units(line, cfg) for line in lines), default=0.0)
    if widest_units <= 0:
        return desired_height_mm, warnings

    max_height_by_width = max_width_mm * 7.0 / widest_units
    fitted = min(desired_height_mm, max_height_by_width)

    if fitted < min_height_mm:
        fitted = min_height_mm
        warnings.append(
            "O texto passou do limite mínimo de legibilidade; revise visualmente ou abrevie o nome."
        )
    return fitted, warnings


def best_compound_break(words: list[str], cfg: TotemConfig) -> list[str]:
    if len(words) <= 1:
        return words
    candidates: list[tuple[float, int, list[str]]] = []
    for cut in range(1, len(words)):
        left = " ".join(words[:cut])
        right = " ".join(words[cut:])
        balance = abs(text_units(left, cfg) - text_units(right, cfg))
        longest = max(text_units(left, cfg), text_units(right, cfg))
        candidates.append((longest, int(balance), [left, right]))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def choose_name_layout(name: str, cfg: TotemConfig) -> TextLayout:
    warnings: list[str] = []
    if not name:
        name = "NOME"
        warnings.append("Nome vazio; usei NOME como exemplo.")

    words = name.split()
    single_height, single_warnings = fit_line_height(
        [name], cfg.desired_name_height_mm, cfg.min_name_height_mm, cfg.max_name_width_mm, cfg
    )

    # Nomes compostos quebram em duas linhas. Nomes simples só reduzem a fonte.
    if len(words) > 1:
        lines = best_compound_break(words, cfg)
        line_height, fit_warnings = fit_line_height(
            lines,
            cfg.desired_compound_line_height_mm,
            cfg.min_name_height_mm,
            cfg.max_name_width_mm,
            cfg,
        )
        total_height = line_height * len(lines) + 2.0 * (len(lines) - 1)
        warnings.extend(fit_warnings)
        return TextLayout(lines=lines, line_height_mm=line_height, total_height_mm=total_height, warnings=warnings)

    warnings.extend(single_warnings)
    return TextLayout(lines=[name], line_height_mm=single_height, total_height_mm=single_height, warnings=warnings)


def rect_element(x: float, y: float, width: float, height: float, klass: str) -> str:
    return (
        f'<rect class="{klass}" x="{fmt(x)}" y="{fmt(y)}" '
        f'width="{fmt(width)}" height="{fmt(height)}" />'
    )


def path_element(d: str, klass: str, extra: str = "") -> str:
    extra_text = f" {extra}" if extra else ""
    return f'<path class="{klass}" d="{d}"{extra_text} />'


def render_grid_text(
    text: str,
    x_center: float,
    y_top: float,
    height_mm: float,
    cfg: TotemConfig,
    klass: str = "cut-internal",
) -> list[str]:
    text = normalize_text(text)
    pitch = height_mm / 7.0
    bridge = clamp(pitch * 0.18, cfg.min_bridge_mm, cfg.max_bridge_mm)
    slot = max(0.15, pitch - bridge)
    width = estimate_text_width(text, height_mm, cfg)
    x_cursor = x_center - width / 2.0

    elements: list[str] = []
    for char_index, ch in enumerate(text):
        if ch == " ":
            x_cursor += cfg.space_units * pitch
        else:
            pattern = FONT_PATTERNS.get(ch)
            if pattern is None:
                x_cursor += (5.0 + cfg.char_gap_units) * pitch
                continue

            for row_index, row in enumerate(pattern):
                run_start: int | None = None
                for col_index, value in enumerate(row + "0"):
                    if value == "1" and run_start is None:
                        run_start = col_index
                    elif value == "0" and run_start is not None:
                        run_len = col_index - run_start
                        x = x_cursor + run_start * pitch + bridge / 2.0
                        y = y_top + row_index * pitch + bridge / 2.0
                        w = run_len * pitch - bridge
                        h = slot
                        elements.append(rect_element(x, y, max(0.15, w), h, klass))
                        run_start = None

            x_cursor += 5.0 * pitch

        if char_index != len(text) - 1:
            x_cursor += cfg.char_gap_units * pitch
    return elements


def player_outline_path(cfg: TotemConfig) -> str:
    # Desenho autoral, paramétrico em escala. Baseado no viewBox V1 128 x 220.
    s = cfg.visible_height_mm / 200.0
    tab_h = cfg.tab_height_mm / s
    tab_w = cfg.tab_width_mm / s
    tab_left = 64.0 - tab_w / 2.0
    tab_right = 64.0 + tab_w / 2.0
    tab_bottom = 208.0 + tab_h

    d = f"""
    M 64 8
    C 51 8 47 18 49 31
    C 50 40 55 48 59 51
    L 52 54
    C 46 56 43 63 40 71
    L 29 62
    C 25 59 20 61 19 66
    L 15 86
    C 14 92 19 97 26 97
    L 39 97
    C 44 97 47 94 46 89
    L 44 82
    L 49 72
    L 50 95
    L 43 145
    L 36 178
    L 27 188
    C 22 193 25 200 32 200
    L 52 200
    L 52 208
    L {tab_left:.3f} 208
    L {tab_left:.3f} {tab_bottom:.3f}
    L {tab_right:.3f} {tab_bottom:.3f}
    L {tab_right:.3f} 208
    L 76 208
    L 76 200
    L 96 200
    C 103 200 106 193 101 188
    L 92 178
    L 85 145
    L 78 95
    L 79 72
    L 84 82
    L 82 89
    C 81 94 84 97 89 97
    L 102 97
    C 109 97 114 92 113 86
    L 109 66
    C 108 61 103 59 99 62
    L 88 71
    C 85 63 82 56 76 54
    L 69 51
    C 73 48 78 40 79 31
    C 81 18 77 8 64 8
    Z
    """
    transform = f'transform="scale({fmt(s)})"'
    return path_element(" ".join(d.split()), "cut-external", transform)


def base_elements(cfg: TotemConfig, x: float, y: float) -> list[str]:
    slot_w = cfg.tab_width_mm + cfg.slot_clearance_mm
    slot_h = cfg.material_thickness_mm + cfg.slot_clearance_mm
    base_w = cfg.base_width_mm
    base_d = cfg.base_depth_mm
    slot_x = x + (base_w - slot_w) / 2.0
    slot_y = y + (base_d - slot_h) / 2.0
    return [
        rect_element(x, y, base_w, base_d, "cut-external"),
        rect_element(slot_x, slot_y, slot_w, slot_h, "cut-internal"),
    ]


def ball_cut_elements(cfg: TotemConfig, x_center: float, y_center: float, radius: float) -> list[str]:
    # Furos simples na bola; cada furo fica separado por pontes de MDF.
    r = radius
    holes = [
        (x_center, y_center, r * 0.18),
        (x_center - r * 0.45, y_center - r * 0.35, r * 0.14),
        (x_center + r * 0.45, y_center - r * 0.35, r * 0.14),
        (x_center - r * 0.38, y_center + r * 0.32, r * 0.14),
        (x_center + r * 0.38, y_center + r * 0.32, r * 0.14),
    ]
    return [
        f'<circle class="engrave" cx="{fmt(x_center)}" cy="{fmt(y_center)}" r="{fmt(radius)}" />',
        *[
            f'<circle class="cut-internal" cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(cr)}" />'
            for cx, cy, cr in holes
        ],
    ]


def generate_totem_svg(nome: str, numero: str, cfg: TotemConfig | None = None) -> GeneratedTotem:
    cfg = cfg or TotemConfig()
    name = normalize_text(nome)
    number = normalize_text(numero)
    number = re.sub(r"[^0-9]", "", number)[:2] or "10"

    warnings: list[str] = []
    unsupported = sorted({ch for ch in name + number if ch not in ALLOWED_CHARS})
    if unsupported:
        warnings.append("Caracteres removidos por não existirem na fonte: " + ", ".join(unsupported))

    dangerous_present = sorted({ch for ch in name + number if ch in DANGEROUS_CHARS})
    if dangerous_present:
        warnings.append(
            "Caracteres com miolo tratados pela fonte TotemStencil: " + ", ".join(dangerous_present)
        )

    name_layout = choose_name_layout(name, cfg)
    warnings.extend(name_layout.warnings)
    number_height, number_warnings = fit_line_height(
        [number], cfg.desired_number_height_mm, cfg.min_number_height_mm, cfg.max_number_width_mm, cfg
    )
    warnings.extend(number_warnings)

    player_w = 128.0 * (cfg.visible_height_mm / 200.0)
    player_total_h = cfg.visible_height_mm + cfg.tab_height_mm + 8.0
    svg_w = max(player_w, cfg.base_width_mm) + 20.0
    svg_h = player_total_h + (cfg.base_depth_mm + 18.0 if cfg.include_base else 10.0)
    x_offset = (svg_w - player_w) / 2.0
    y_offset = 0.0
    s = cfg.visible_height_mm / 200.0

    torso_center_x = x_offset + 64.0 * s
    name_y = y_offset + 82.0 * s
    if len(name_layout.lines) == 2:
        name_y = y_offset + 78.0 * s
    number_y = y_offset + 111.0 * s

    elements_external = [
        f'<g id="CORTE_CORPO" transform="translate({fmt(x_offset)} {fmt(y_offset)})">',
        player_outline_path(cfg),
        "</g>",
    ]

    elements_internal: list[str] = ['<g id="CORTE_INTERNO_TEXTO">']
    current_y = name_y
    for line in name_layout.lines:
        elements_internal.extend(render_grid_text(line, torso_center_x, current_y, name_layout.line_height_mm, cfg))
        current_y += name_layout.line_height_mm + 2.0
    elements_internal.extend(render_grid_text(number, torso_center_x, number_y, number_height, cfg))
    elements_internal.extend(ball_cut_elements(cfg, torso_center_x, y_offset + 190.0 * s, 10.0 * s))
    elements_internal.append("</g>")

    elements_base: list[str] = []
    if cfg.include_base:
        base_x = (svg_w - cfg.base_width_mm) / 2.0
        base_y = cfg.visible_height_mm + cfg.tab_height_mm + 14.0
        elements_base = ['<g id="CORTE_BASE">', *base_elements(cfg, base_x, base_y), "</g>"]

    preview: list[str] = []
    if cfg.include_preview:
        preview.extend([
            '<g id="PREVIEW" opacity="0.18">',
            f'<rect x="0" y="0" width="{fmt(svg_w)}" height="{fmt(svg_h)}" fill="white" />',
            "</g>",
        ])

    style = """
    <style>
      .cut-external { fill: none; stroke: #ff0000; stroke-width: 0.12; vector-effect: non-scaling-stroke; }
      .cut-internal { fill: none; stroke: #0000ff; stroke-width: 0.12; vector-effect: non-scaling-stroke; }
      .engrave { fill: none; stroke: #00aa00; stroke-width: 0.12; vector-effect: non-scaling-stroke; }
      text { font-family: Arial, sans-serif; }
    </style>
    """

    metadata = "\n".join(
        f"    <!-- {escape(line)} -->" for line in [
            f"Nome normalizado: {name}",
            f"Numero normalizado: {number}",
            f"Altura visivel: {cfg.visible_height_mm} mm",
            f"MDF: {cfg.material_thickness_mm} mm",
            f"Folga do encaixe: {cfg.slot_clearance_mm} mm",
            f"Linhas do nome: {' / '.join(name_layout.lines)}",
            *warnings,
        ]
    )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(svg_w)}mm" height="{fmt(svg_h)}mm" viewBox="0 0 {fmt(svg_w)} {fmt(svg_h)}">
{style}
  <title>Totem Futebol - {escape(name)} {escape(number)}</title>
  <desc>Arquivo de corte gerado automaticamente. Vermelho: corte externo. Azul: corte interno. Verde: gravação/opcional.</desc>
{metadata}
  {''.join(preview)}
  {''.join(elements_external)}
  {''.join(elements_internal)}
  {''.join(elements_base)}
</svg>
"""
    return GeneratedTotem(
        svg=svg,
        normalized_name=name,
        normalized_number=number,
        name_lines=name_layout.lines,
        warnings=warnings,
    )


def safe_filename(nome: str, numero: str, suffix: str = "svg") -> str:
    base = normalize_text(f"{nome}_{numero}") or "TOTEM"
    base = base.replace(" ", "_")
    base = re.sub(r"[^A-Z0-9_\-]+", "", base)
    return f"{base}.{suffix.lstrip('.')}"
