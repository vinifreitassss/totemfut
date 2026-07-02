from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re

from . import generator as base
from .template_loader import Rect, load_base_template, load_player_template

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
    tab_width_mm: float = 50.0
    tab_height_mm: float = 12.0
    max_name_width_mm: float = 44.0
    max_number_width_mm: float = 38.0
    desired_name_height_mm: float = 9.8
    desired_compound_line_height_mm: float = 8.2
    desired_number_height_mm: float = 31.0
    min_name_height_mm: float = 6.2
    min_number_height_mm: float = 24.0
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


def _name_layout(name: str, zone: Rect, cfg: TotemConfig, renderer=None) -> TextLayout:
    warnings: list[str] = []
    if not name:
        name = "NOME"
        warnings.append("Nome vazio; usei NOME como exemplo.")

    words = name.split()
    max_width = zone.width * 0.96

    if len(words) > 1:
        lines = _break_compound(words, cfg, renderer)
        desired = min(cfg.desired_compound_line_height_mm, zone.height * 0.42)
        minimum = min(cfg.min_name_height_mm, max(3.8, zone.height * 0.33))
        line_height, fit_warnings = _fit_height(lines, desired, minimum, max_width, cfg, renderer)
        total_height = line_height * len(lines) + 1.6 * (len(lines) - 1)
        if total_height > zone.height * 0.92:
            line_height = (zone.height * 0.92 - 1.6 * (len(lines) - 1)) / len(lines)
        warnings.extend(fit_warnings)
        return TextLayout(lines, line_height, warnings)

    desired = min(cfg.desired_name_height_mm, zone.height * 0.76)
    minimum = min(cfg.min_name_height_mm, max(4.0, zone.height * 0.45))
    line_height, fit_warnings = _fit_height([name], desired, minimum, max_width, cfg, renderer)
    warnings.extend(fit_warnings)
    return TextLayout([name], line_height, warnings)


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


def _transform(tx: float, ty: float, scale: float, origin: Rect) -> str:
    return (
        f"translate({base.fmt(tx)} {base.fmt(ty)}) "
        f"scale({base.fmt(scale)}) "
        f"translate({base.fmt(-origin.x)} {base.fmt(-origin.y)})"
    )


def _template_paths(tx: float, ty: float, scale: float, origin: Rect) -> tuple[list[str], list[str]]:
    template = load_player_template()
    transform = _transform(tx, ty, scale, origin)

    preview = [
        f'<path class="preview-fill" d="{template.outer.d}" transform="{transform}" />'
    ]
    cut = [
        f'<path class="cut-external" d="{template.outer.d}" transform="{transform}" />'
    ]

    for shape in template.internal_paths:
        preview.append(f'<path class="preview-hole" d="{shape.d}" transform="{transform}" />')
        cut.append(f'<path class="cut-internal" d="{shape.d}" transform="{transform}" />')

    return preview, cut


def _base_elements(base_x: float, base_y: float, cfg: TotemConfig) -> tuple[list[str], list[str], float]:
    template = load_base_template()
    scale = cfg.base_width_mm / template.outer.width
    base_h = template.outer.height * scale

    # A largura do rasgo vem do desenho; a altura vem do MDF real.
    slot_ratio = template.slot.width / template.outer.width
    slot_w = max(cfg.tab_width_mm + cfg.slot_clearance_mm, cfg.base_width_mm * slot_ratio)
    slot_h = cfg.material_thickness_mm + cfg.slot_clearance_mm
    slot_x = base_x + (cfg.base_width_mm - slot_w) / 2.0
    slot_y = base_y + (base_h - slot_h) / 2.0

    preview = [
        base.rect_element(base_x, base_y, cfg.base_width_mm, base_h, "preview-fill"),
        base.rect_element(slot_x, slot_y, slot_w, slot_h, "preview-hole"),
    ]
    cut = [
        base.rect_element(base_x, base_y, cfg.base_width_mm, base_h, "cut-external"),
        base.rect_element(slot_x, slot_y, slot_w, slot_h, "cut-internal"),
    ]
    return preview, cut, base_h


def generate_totem_svg(nome: str, numero: str, cfg: TotemConfig | None = None) -> GeneratedTotem:
    cfg = cfg or TotemConfig()
    name = base.normalize_text(nome)
    number = re.sub(r"[^0-9]", "", base.normalize_text(numero))[:2] or "10"
    renderer = _renderer(cfg, name, number)

    player = load_player_template()
    player_scale = cfg.visible_height_mm / player.bbox.height
    player_w = player.bbox.width * player_scale
    margin = 8.0

    base_preview: list[str] = []
    base_cut: list[str] = []
    base_h = 0.0
    base_gap = 10.0 if cfg.include_base else 0.0
    if cfg.include_base:
        _, _, base_h = _base_elements(0, 0, cfg)

    svg_w = max(player_w, cfg.base_width_mm) + margin * 2.0
    svg_h = cfg.visible_height_mm + base_gap + base_h + margin * 2.0
    player_x = (svg_w - player_w) / 2.0
    player_y = margin

    name_zone = player.name_zone.transformed(player_x, player_y, player_scale, player.bbox)
    number_zone = Rect(
        name_zone.x + name_zone.width * 0.18,
        name_zone.y2 + max(3.0, name_zone.height * 0.30),
        name_zone.width * 0.64,
        cfg.visible_height_mm * 0.22,
    )

    warnings: list[str] = []
    if renderer is not None:
        warnings.append(f"Texto renderizado em curvas pela fonte instalada: {renderer.font_name}.")
    else:
        dangerous = sorted({ch for ch in name + number if ch in base.DANGEROUS_CHARS})
        if dangerous:
            warnings.append("Caracteres com miolo tratados pela fonte modular TotemStencil: " + ", ".join(dangerous))
        warnings.append("Fonte STENCIL.TTF não encontrada; usei a fonte modular segura da V1.")

    layout = _name_layout(name, name_zone, cfg, renderer)
    warnings.extend(layout.warnings)
    number_height, number_warnings = _fit_height(
        [number],
        min(cfg.desired_number_height_mm, number_zone.height * 0.88),
        cfg.min_number_height_mm,
        number_zone.width,
        cfg,
        renderer,
    )
    warnings.extend(number_warnings)

    template_preview, template_cut = _template_paths(player_x, player_y, player_scale, player.bbox)

    if cfg.include_base:
        base_x = (svg_w - cfg.base_width_mm) / 2.0
        base_y = margin + cfg.visible_height_mm + base_gap
        base_preview, base_cut, _base_h = _base_elements(base_x, base_y, cfg)

    text_cut = ['<g id="CORTE_INTERNO_TEXTO">']
    text_preview = ['<g id="PREVIEW_TEXTO">']
    total_name_h = layout.line_height_mm * len(layout.lines) + 1.6 * (len(layout.lines) - 1)
    y = name_zone.y + (name_zone.height - total_name_h) / 2.0
    for line in layout.lines:
        text_cut.extend(_render_text(line, name_zone.cx, y, layout.line_height_mm, cfg, "cut-internal", renderer))
        text_preview.extend(_render_text(line, name_zone.cx, y, layout.line_height_mm, cfg, "preview-hole", renderer))
        y += layout.line_height_mm + 1.6

    number_y = number_zone.y + (number_zone.height - number_height) / 2.0
    text_cut.extend(_render_text(number, number_zone.cx, number_y, number_height, cfg, "cut-internal", renderer))
    text_preview.extend(_render_text(number, number_zone.cx, number_y, number_height, cfg, "preview-hole", renderer))
    text_cut.append("</g>")
    text_preview.append("</g>")

    preview = [
        '<g id="PREVIEW_PRODUTO">',
        *template_preview,
        *base_preview,
        *text_preview,
        "</g>",
    ] if cfg.include_preview else []

    style = """
    <style>
      .cut-external { fill: none; stroke: #ff0000; stroke-width: 0.12; vector-effect: non-scaling-stroke; }
      .cut-internal { fill: none; stroke: #0000ff; stroke-width: 0.12; vector-effect: non-scaling-stroke; }
      .preview-fill { fill: #111111; stroke: none; fill-rule: evenodd; }
      .preview-hole { fill: #ffffff; stroke: none; fill-rule: evenodd; }
    </style>
    """
    metadata = "\n".join(
        f"    <!-- {escape(line)} -->" for line in [
            f"Nome normalizado: {name}",
            f"Numero normalizado: {number}",
            f"Altura visivel do corpo: {cfg.visible_height_mm} mm",
            f"MDF: {cfg.material_thickness_mm} mm",
            f"Folga do encaixe: {cfg.slot_clearance_mm} mm",
            f"Zona do nome vem do retangulo guia do CORPO.svg",
            f"Linhas do nome: {' / '.join(layout.lines)}",
            *warnings,
        ]
    )
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{base.fmt(svg_w)}mm" height="{base.fmt(svg_h)}mm" viewBox="0 0 {base.fmt(svg_w)} {base.fmt(svg_h)}">
{style}
  <title>Totem Futebol - {escape(name)} {escape(number)}</title>
  <desc>Arquivo de corte gerado automaticamente usando assets/CORPO.svg e assets/SVG_BASE.svg.</desc>
{metadata}
  {''.join(preview)}
  <g id="CORTE_CORPO">{''.join(template_cut)}</g>
  {''.join(text_cut)}
  <g id="CORTE_BASE">{''.join(base_cut)}</g>
</svg>
"""
    return GeneratedTotem(svg=svg, normalized_name=name, normalized_number=number, name_lines=layout.lines, warnings=warnings)
