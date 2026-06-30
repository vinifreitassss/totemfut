from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re

from . import generator as base

try:
    from .font_renderer import FontTextRenderer
except Exception:  # pragma: no cover
    FontTextRenderer = None  # type: ignore


@dataclass(slots=True)
class TotemConfig:
    visible_height_mm: float = 200.0
    material_thickness_mm: float = 3.0
    slot_clearance_mm: float = 0.25
    base_width_mm: float = 130.0
    base_depth_mm: float = 50.0
    tab_width_mm: float = 48.0
    tab_height_mm: float = 12.0
    max_name_width_mm: float = 58.0
    max_number_width_mm: float = 50.0
    desired_name_height_mm: float = 13.0
    desired_compound_line_height_mm: float = 10.5
    desired_number_height_mm: float = 40.0
    min_name_height_mm: float = 7.0
    min_number_height_mm: float = 28.0
    min_bridge_mm: float = 0.45
    max_bridge_mm: float = 1.25
    char_gap_units: float = 0.8
    space_units: float = 2.4
    include_base: bool = True
    include_preview: bool = True
    use_installed_stencil_font: bool = True


GeneratedTotem = base.GeneratedTotem
safe_filename = base.safe_filename


@dataclass(slots=True)
class TextLayout:
    lines: list[str]
    line_height_mm: float
    warnings: list[str]


def _width_per_height(text: str, cfg: TotemConfig, renderer=None) -> float:
    if renderer is not None:
        try:
            return renderer.width_per_height(text)
        except Exception:
            pass
    return base.text_units(text, cfg) / 7.0


def _fit_height(lines: list[str], desired: float, minimum: float, max_width: float, cfg: TotemConfig, renderer=None) -> tuple[float, list[str]]:
    warnings: list[str] = []
    ratio = max((_width_per_height(line, cfg, renderer) for line in lines), default=0.0)
    if ratio <= 0:
        return desired, warnings
    fitted = min(desired, max_width / ratio)
    if fitted < minimum:
        fitted = minimum
        warnings.append("O texto passou do limite mínimo; revise visualmente ou abrevie o nome.")
    return fitted, warnings


def _break_compound(words: list[str], cfg: TotemConfig, renderer=None) -> list[str]:
    if len(words) <= 1:
        return words
    candidates: list[tuple[float, float, list[str]]] = []
    for cut in range(1, len(words)):
        left = " ".join(words[:cut])
        right = " ".join(words[cut:])
        lw = _width_per_height(left, cfg, renderer)
        rw = _width_per_height(right, cfg, renderer)
        candidates.append((max(lw, rw), abs(lw - rw), [left, right]))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _name_layout(name: str, cfg: TotemConfig, renderer=None) -> TextLayout:
    warnings: list[str] = []
    if not name:
        name = "NOME"
        warnings.append("Nome vazio; usei NOME como exemplo.")
    words = name.split()
    if len(words) > 1:
        lines = _break_compound(words, cfg, renderer)
        height, fit_warnings = _fit_height(
            lines,
            cfg.desired_compound_line_height_mm,
            cfg.min_name_height_mm,
            cfg.max_name_width_mm,
            cfg,
            renderer,
        )
        warnings.extend(fit_warnings)
        return TextLayout(lines, height, warnings)
    height, fit_warnings = _fit_height([name], cfg.desired_name_height_mm, cfg.min_name_height_mm, cfg.max_name_width_mm, cfg, renderer)
    warnings.extend(fit_warnings)
    return TextLayout([name], height, warnings)


def _renderer(cfg: TotemConfig, name: str, number: str):
    if not cfg.use_installed_stencil_font or FontTextRenderer is None:
        return None
    try:
        renderer = FontTextRenderer.try_default()
    except Exception:
        return None
    if renderer is not None and renderer.can_render(name + number):
        return renderer
    return None


def _render_text(text: str, x: float, y: float, height: float, cfg: TotemConfig, klass: str, renderer=None) -> list[str]:
    if renderer is not None:
        try:
            return renderer.render_line(text, x, y, height, klass)
        except Exception:
            pass
    return base.render_grid_text(text, x, y, height, cfg, klass)


def _player_outline_d(cfg: TotemConfig) -> str:
    s = cfg.visible_height_mm / 200.0
    tab_h = cfg.tab_height_mm / s
    tab_w = cfg.tab_width_mm / s
    tab_left = 70.0 - tab_w / 2.0
    tab_right = 70.0 + tab_w / 2.0
    tab_bottom = 204.0 + tab_h
    d = f"""
    M 70 5
    C 58 5 51 15 52 29
    C 53 40 59 48 64 51
    L 54 55
    C 47 58 43 66 39 77
    L 29 69
    C 24 65 18 68 17 74
    L 8 96
    C 5 104 10 111 19 111
    L 33 111
    C 39 111 42 106 40 100
    L 38 91
    L 45 78
    L 47 118
    C 47 127 44 136 41 145
    L 35 166
    L 31 185
    L 19 195
    C 13 200 17 207 25 207
    L 49 207
    L {tab_left:.3f} 207
    L {tab_left:.3f} {tab_bottom:.3f}
    L {tab_right:.3f} {tab_bottom:.3f}
    L {tab_right:.3f} 207
    L 91 207
    L 115 207
    C 123 207 127 200 121 195
    L 109 185
    L 105 166
    L 99 145
    C 96 136 93 127 93 118
    L 95 78
    L 102 91
    L 100 100
    C 98 106 101 111 107 111
    L 121 111
    C 130 111 135 104 132 96
    L 123 74
    C 122 68 116 65 111 69
    L 101 77
    C 97 66 93 58 86 55
    L 76 51
    C 81 48 87 40 88 29
    C 89 15 82 5 70 5
    Z
    """
    return " ".join(d.split())


def _base_elements(cfg: TotemConfig, x: float, y: float, outer: str, inner: str) -> list[str]:
    slot_w = cfg.tab_width_mm + cfg.slot_clearance_mm
    slot_h = cfg.material_thickness_mm + cfg.slot_clearance_mm
    slot_x = x + (cfg.base_width_mm - slot_w) / 2.0
    slot_y = y + (cfg.base_depth_mm - slot_h) / 2.0
    return [
        base.rect_element(x, y, cfg.base_width_mm, cfg.base_depth_mm, outer),
        base.rect_element(slot_x, slot_y, slot_w, slot_h, inner),
    ]


def _ball(cx: float, cy: float, r: float, klass: str) -> list[str]:
    holes = [
        (cx, cy, r * 0.18),
        (cx - r * 0.45, cy - r * 0.35, r * 0.14),
        (cx + r * 0.45, cy - r * 0.35, r * 0.14),
        (cx - r * 0.38, cy + r * 0.32, r * 0.14),
        (cx + r * 0.38, cy + r * 0.32, r * 0.14),
    ]
    return [
        f'<circle class="engrave" cx="{base.fmt(cx)}" cy="{base.fmt(cy)}" r="{base.fmt(r)}" />',
        *[f'<circle class="{klass}" cx="{base.fmt(x)}" cy="{base.fmt(y)}" r="{base.fmt(hr)}" />' for x, y, hr in holes],
    ]


def _shirt_guides(x_offset: float, y_offset: float, s: float) -> list[str]:
    cx = x_offset + 70.0 * s
    return [
        f'<path class="engrave" d="M {base.fmt(x_offset + 48*s)} {base.fmt(y_offset + 63*s)} C {base.fmt(cx-14*s)} {base.fmt(y_offset + 72*s)} {base.fmt(cx+14*s)} {base.fmt(y_offset + 72*s)} {base.fmt(x_offset + 92*s)} {base.fmt(y_offset + 63*s)}" />',
        f'<path class="engrave" d="M {base.fmt(x_offset + 47*s)} {base.fmt(y_offset + 118*s)} C {base.fmt(cx-7*s)} {base.fmt(y_offset + 126*s)} {base.fmt(cx+7*s)} {base.fmt(y_offset + 126*s)} {base.fmt(x_offset + 93*s)} {base.fmt(y_offset + 118*s)}" />',
    ]


def generate_totem_svg(nome: str, numero: str, cfg: TotemConfig | None = None) -> GeneratedTotem:
    cfg = cfg or TotemConfig()
    name = base.normalize_text(nome)
    number = re.sub(r"[^0-9]", "", base.normalize_text(numero))[:2] or "10"
    renderer = _renderer(cfg, name, number)

    warnings: list[str] = []
    if renderer is not None:
        warnings.append(f"Texto renderizado em curvas pela fonte instalada: {renderer.font_name}.")
    else:
        dangerous = sorted({ch for ch in name + number if ch in base.DANGEROUS_CHARS})
        if dangerous:
            warnings.append("Caracteres com miolo tratados pela fonte modular TotemStencil: " + ", ".join(dangerous))
        warnings.append("Fonte STENCIL.TTF não encontrada; usei a fonte modular segura da V1.")

    layout = _name_layout(name, cfg, renderer)
    warnings.extend(layout.warnings)
    number_height, number_warnings = _fit_height([number], cfg.desired_number_height_mm, cfg.min_number_height_mm, cfg.max_number_width_mm, cfg, renderer)
    warnings.extend(number_warnings)

    s = cfg.visible_height_mm / 200.0
    player_w = 140.0 * s
    svg_w = max(player_w, cfg.base_width_mm) + 20.0
    svg_h = cfg.visible_height_mm + cfg.tab_height_mm + 8.0 + (cfg.base_depth_mm + 18.0 if cfg.include_base else 10.0)
    x_offset = (svg_w - player_w) / 2.0
    y_offset = 0.0
    torso_x = x_offset + 70.0 * s
    name_y = y_offset + (68.0 if len(layout.lines) == 2 else 72.0) * s
    number_y = y_offset + 92.0 * s

    cut_text = ['<g id="CORTE_INTERNO_TEXTO">']
    preview_text = ['<g id="PREVIEW_TEXTO">']
    y = name_y
    for line in layout.lines:
        cut_text.extend(_render_text(line, torso_x, y, layout.line_height_mm, cfg, "cut-internal", renderer))
        preview_text.extend(_render_text(line, torso_x, y, layout.line_height_mm, cfg, "preview-hole", renderer))
        y += layout.line_height_mm + 2.0
    cut_text.extend(_render_text(number, torso_x, number_y, number_height, cfg, "cut-internal", renderer))
    preview_text.extend(_render_text(number, torso_x, number_y, number_height, cfg, "preview-hole", renderer))
    cut_text.extend(_ball(torso_x, y_offset + 188.0 * s, 9.0 * s, "cut-internal"))
    preview_text.extend(_ball(torso_x, y_offset + 188.0 * s, 9.0 * s, "preview-hole"))
    cut_text.append("</g>")
    preview_text.append("</g>")

    base_cut: list[str] = []
    base_preview: list[str] = []
    if cfg.include_base:
        bx = (svg_w - cfg.base_width_mm) / 2.0
        by = cfg.visible_height_mm + cfg.tab_height_mm + 14.0
        base_cut = ['<g id="CORTE_BASE">', *_base_elements(cfg, bx, by, "cut-external", "cut-internal"), "</g>"]
        base_preview = ['<g id="PREVIEW_BASE">', *_base_elements(cfg, bx, by, "preview-fill", "preview-hole"), "</g>"]

    player_d = _player_outline_d(cfg)
    preview = [
        '<g id="PREVIEW_PRODUTO">',
        f'<path class="preview-fill" d="{player_d}" transform="translate({base.fmt(x_offset)} {base.fmt(y_offset)}) scale({base.fmt(s)})" />',
        *base_preview,
        *preview_text,
        "</g>",
    ] if cfg.include_preview else []

    style = """
    <style>
      .cut-external { fill: none; stroke: #ff0000; stroke-width: 0.12; vector-effect: non-scaling-stroke; }
      .cut-internal { fill: none; stroke: #0000ff; stroke-width: 0.12; vector-effect: non-scaling-stroke; }
      .engrave { fill: none; stroke: #00aa00; stroke-width: 0.12; vector-effect: non-scaling-stroke; }
      .preview-fill { fill: #111111; stroke: none; fill-rule: evenodd; }
      .preview-hole { fill: #ffffff; stroke: none; fill-rule: evenodd; }
    </style>
    """
    metadata = "\n".join(
        f"    <!-- {escape(line)} -->" for line in [
            f"Nome normalizado: {name}",
            f"Numero normalizado: {number}",
            f"Altura visivel: {cfg.visible_height_mm} mm",
            f"MDF: {cfg.material_thickness_mm} mm",
            f"Folga do encaixe: {cfg.slot_clearance_mm} mm",
            f"Linhas do nome: {' / '.join(layout.lines)}",
            *warnings,
        ]
    )
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{base.fmt(svg_w)}mm" height="{base.fmt(svg_h)}mm" viewBox="0 0 {base.fmt(svg_w)} {base.fmt(svg_h)}">
{style}
  <title>Totem Futebol - {escape(name)} {escape(number)}</title>
  <desc>Arquivo de corte gerado automaticamente. Vermelho: corte externo. Azul: corte interno. Verde: gravação/opcional.</desc>
{metadata}
  {''.join(preview)}
  <g id="CORTE_CORPO" transform="translate({base.fmt(x_offset)} {base.fmt(y_offset)}) scale({base.fmt(s)})"><path class="cut-external" d="{player_d}" /></g>
  <g id="GRAVACAO_OPCIONAL">{''.join(_shirt_guides(x_offset, y_offset, s))}</g>
  {''.join(cut_text)}
  {''.join(base_cut)}
</svg>
"""
    return GeneratedTotem(svg=svg, normalized_name=name, normalized_number=number, name_lines=layout.lines, warnings=warnings)
