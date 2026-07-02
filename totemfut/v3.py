from __future__ import annotations

from html import escape
import re
import unicodedata

from . import generator as base
from . import v2 as old
from .template_loader import Rect, load_player_template

GeneratedTotem = base.GeneratedTotem
TotemConfig = old.TotemConfig
safe_filename = base.safe_filename


def _normalize_display_name(raw: str) -> str:
    text = (raw or "").strip().upper()
    kept: list[str] = []
    for ch in text:
        category = unicodedata.category(ch)
        if ch.isdigit() or ch in " -" or category.startswith("L"):
            kept.append(ch)
    return re.sub(r"\s+", " ", "".join(kept)).strip()


def _name_layout(name: str, zone: Rect, cfg: TotemConfig, renderer=None) -> old.TextLayout:
    warnings: list[str] = []
    if not name:
        name = "NOME"
        warnings.append("Nome vazio; usei NOME como exemplo.")

    words = name.split()
    max_width = zone.width * 0.96

    if len(words) > 1:
        lines = old._break_compound(words, cfg, renderer)
        desired = min(cfg.desired_compound_line_height_mm * 1.35, zone.height * 0.44)
        minimum = min(cfg.min_name_height_mm, max(4.4, zone.height * 0.32))
        line_height, fit_warnings = old._fit_height(lines, desired, minimum, max_width, cfg, renderer)
        total_height = line_height * len(lines) + 1.8 * (len(lines) - 1)
        if total_height > zone.height * 0.94:
            line_height = (zone.height * 0.94 - 1.8 * (len(lines) - 1)) / len(lines)
        warnings.extend(fit_warnings)
        return old.TextLayout(lines, line_height, warnings)

    desired = min(cfg.desired_name_height_mm, zone.height * 0.78)
    minimum = min(cfg.min_name_height_mm, max(4.2, zone.height * 0.45))
    line_height, fit_warnings = old._fit_height([name], desired, minimum, max_width, cfg, renderer)
    warnings.extend(fit_warnings)
    return old.TextLayout([name], line_height, warnings)


def _build_name_zone(guide_zone: Rect, player_x: float, player_y: float, player_w: float, player_h: float, is_compound: bool) -> Rect:
    if not is_compound:
        return guide_zone
    return Rect(player_x + player_w * 0.15, player_y + player_h * 0.205, player_w * 0.70, player_h * 0.145)


def _build_number_zone(player_x: float, player_y: float, player_w: float, player_h: float, digits: int) -> Rect:
    if digits <= 1:
        return Rect(player_x + player_w * 0.34, player_y + player_h * 0.43, player_w * 0.32, player_h * 0.22)
    return Rect(player_x + player_w * 0.25, player_y + player_h * 0.445, player_w * 0.50, player_h * 0.17)


def _render_text(text: str, x: float, y: float, height: float, cfg: TotemConfig, klass: str, renderer=None) -> list[str]:
    if renderer is not None:
        try:
            return renderer.render_line(text, x, y, height, klass)
        except Exception:
            pass
    return base.render_grid_text(base.normalize_text(text), x, y, height, cfg, klass)


def generate_totem_svg(nome: str, numero: str, cfg: TotemConfig | None = None) -> GeneratedTotem:
    cfg = cfg or TotemConfig()

    display_name = _normalize_display_name(nome)
    fallback_name = base.normalize_text(nome)
    number = re.sub(r"[^0-9]", "", base.normalize_text(numero))[:2] or "10"
    renderer = old._renderer(cfg, display_name, number)
    name = display_name if renderer is not None else fallback_name

    player = load_player_template()
    player_scale = cfg.visible_height_mm / player.bbox.height
    player_w = player.bbox.width * player_scale
    margin = 8.0

    base_preview: list[str] = []
    base_cut: list[str] = []
    base_h = 0.0
    base_gap = 10.0 if cfg.include_base else 0.0
    if cfg.include_base:
        _, _, base_h = old._base_elements(0, 0, cfg)

    svg_w = max(player_w, cfg.base_width_mm) + margin * 2.0
    svg_h = cfg.visible_height_mm + base_gap + base_h + margin * 2.0
    player_x = (svg_w - player_w) / 2.0
    player_y = margin

    guide_zone = player.name_zone.transformed(player_x, player_y, player_scale, player.bbox)
    is_compound = " " in name.strip()
    name_zone = _build_name_zone(guide_zone, player_x, player_y, player_w, cfg.visible_height_mm, is_compound)
    number_zone = _build_number_zone(player_x, player_y, player_w, cfg.visible_height_mm, len(number))

    warnings: list[str] = []
    if renderer is not None:
        warnings.append(f"Texto renderizado em curvas pela fonte instalada: {renderer.font_name}.")
    else:
        dangerous = sorted({ch for ch in name + number if ch in base.DANGEROUS_CHARS})
        if dangerous:
            warnings.append("Caracteres com miolo tratados pela fonte modular TotemStencil: " + ", ".join(dangerous))
        warnings.append("Fonte STENCIL.TTF sem suporte completo ou não encontrada; usei a fonte modular segura sem acentos.")

    layout = _name_layout(name, name_zone, cfg, renderer)
    warnings.extend(layout.warnings)

    desired_number_height = min(cfg.desired_number_height_mm * (0.74 if len(number) >= 2 else 1.0), number_zone.height * 0.92)
    min_number_height = cfg.min_number_height_mm * (0.84 if len(number) >= 2 else 1.0)
    max_number_width = number_zone.width * (0.94 if len(number) >= 2 else 1.0)
    number_height, number_warnings = old._fit_height([number], desired_number_height, min_number_height, max_number_width, cfg, renderer)
    warnings.extend(number_warnings)

    template_preview, template_cut = old._template_paths(player_x, player_y, player_scale, player.bbox)

    if cfg.include_base:
        base_x = (svg_w - cfg.base_width_mm) / 2.0
        base_y = margin + cfg.visible_height_mm + base_gap
        base_preview, base_cut, _base_h = old._base_elements(base_x, base_y, cfg)

    text_cut = ['<g id="CORTE_INTERNO_TEXTO">']
    text_preview = ['<g id="PREVIEW_TEXTO">']

    line_gap = 1.8 if len(layout.lines) > 1 else 0.0
    total_name_h = layout.line_height_mm * len(layout.lines) + line_gap * (len(layout.lines) - 1)
    y = name_zone.y + (name_zone.height - total_name_h) / 2.0
    for line in layout.lines:
        text_cut.extend(_render_text(line, name_zone.cx, y, layout.line_height_mm, cfg, "cut-internal", renderer))
        text_preview.extend(_render_text(line, name_zone.cx, y, layout.line_height_mm, cfg, "preview-hole", renderer))
        y += layout.line_height_mm + line_gap

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
            f"Zona do nome: {'zona ampliada' if is_compound else 'retangulo guia do CORPO.svg'}",
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
