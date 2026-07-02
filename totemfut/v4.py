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


def _render_text(text: str, x: float, y: float, height: float, cfg: TotemConfig, klass: str, renderer=None) -> list[str]:
    if renderer is not None:
        try:
            return renderer.render_line(text, x, y, height, klass)
        except Exception:
            pass
    return base.render_grid_text(base.normalize_text(text), x, y, height, cfg, klass)


def _single_name_layout(name: str, zone: Rect, cfg: TotemConfig, renderer=None) -> old.TextLayout:
    # Regra: nome simples usa o retângulo original e preenche melhor a altura.
    desired = min(12.0, zone.height * 0.90)
    minimum = min(cfg.min_name_height_mm, max(5.0, zone.height * 0.48))
    line_height, warnings = old._fit_height([name], desired, minimum, zone.width * 0.96, cfg, renderer)
    return old.TextLayout([name], line_height, warnings)


def _compound_name_layout(name: str, zone: Rect, cfg: TotemConfig, renderer=None) -> old.TextLayout:
    # Regra: nome composto sempre quebra em duas linhas e usa a maior linha para definir a escala.
    words = name.split()
    if len(words) <= 1:
        return _single_name_layout(name, zone, cfg, renderer)
    lines = old._break_compound(words, cfg, renderer)
    desired = min(11.2, zone.height * 0.42)
    minimum = min(cfg.min_name_height_mm, max(4.6, zone.height * 0.26))
    line_height, warnings = old._fit_height(lines, desired, minimum, zone.width * 0.96, cfg, renderer)
    line_gap = 1.4
    total_h = line_height * len(lines) + line_gap * (len(lines) - 1)
    if total_h > zone.height * 0.96:
        line_height = (zone.height * 0.96 - line_gap * (len(lines) - 1)) / len(lines)
    return old.TextLayout(lines, line_height, warnings)


def _name_zone(guide: Rect, is_compound: bool) -> Rect:
    if not is_compound:
        return guide
    # Regra: composto respeita as linhas da camisa. Não vai para cima do ombro nem abre até o braço.
    return Rect(
        guide.x,
        guide.y + guide.height * 0.12,
        guide.width,
        guide.height * 2.20,
    )


def _number_rules(player_x: float, player_y: float, player_w: float, player_h: float, digits: int) -> tuple[float, float, float, float]:
    # Regra: a posição aprovada do número não muda. Só muda a escala quando for dezena.
    center_x = player_x + player_w * 0.50
    top_y = player_y + player_h * 0.462
    if digits <= 1:
        height = 31.0
        max_width = player_w * 0.34
    else:
        height = 23.5
        max_width = player_w * 0.50
    return center_x, top_y, height, max_width


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

    base_h = 0.0
    base_gap = 10.0 if cfg.include_base else 0.0
    if cfg.include_base:
        _, _, base_h = old._base_elements(0, 0, cfg)

    svg_w = max(player_w, cfg.base_width_mm) + margin * 2.0
    svg_h = cfg.visible_height_mm + base_gap + base_h + margin * 2.0
    player_x = (svg_w - player_w) / 2.0
    player_y = margin

    guide = player.name_zone.transformed(player_x, player_y, player_scale, player.bbox)
    is_compound = " " in name.strip()
    zone_name = _name_zone(guide, is_compound)
    layout = _compound_name_layout(name, zone_name, cfg, renderer) if is_compound else _single_name_layout(name, zone_name, cfg, renderer)

    center_num_x, number_y, desired_number_height, max_number_width = _number_rules(
        player_x,
        player_y,
        player_w,
        cfg.visible_height_mm,
        len(number),
    )
    number_height, number_warnings = old._fit_height(
        [number],
        desired_number_height,
        min(desired_number_height, cfg.min_number_height_mm),
        max_number_width,
        cfg,
        renderer,
    )

    warnings: list[str] = []
    if renderer is not None:
        warnings.append(f"Texto renderizado em curvas pela fonte instalada: {renderer.font_name}.")
    else:
        dangerous = sorted({ch for ch in name + number if ch in base.DANGEROUS_CHARS})
        if dangerous:
            warnings.append("Caracteres com miolo tratados pela fonte modular TotemStencil: " + ", ".join(dangerous))
        warnings.append("Fonte STENCIL.TTF sem suporte completo ou não encontrada; usei a fonte modular segura sem acentos.")
    warnings.extend(layout.warnings)
    warnings.extend(number_warnings)

    template_preview, template_cut = old._template_paths(player_x, player_y, player_scale, player.bbox)

    base_preview: list[str] = []
    base_cut: list[str] = []
    if cfg.include_base:
        base_x = (svg_w - cfg.base_width_mm) / 2.0
        base_y = margin + cfg.visible_height_mm + base_gap
        base_preview, base_cut, _base_h = old._base_elements(base_x, base_y, cfg)

    text_cut = ['<g id="CORTE_INTERNO_TEXTO">']
    text_preview = ['<g id="PREVIEW_TEXTO">']

    line_gap = 1.4 if len(layout.lines) > 1 else 0.0
    total_name_h = layout.line_height_mm * len(layout.lines) + line_gap * (len(layout.lines) - 1)
    y = zone_name.y + (zone_name.height - total_name_h) / 2.0
    for line in layout.lines:
        text_cut.extend(_render_text(line, zone_name.cx, y, layout.line_height_mm, cfg, "cut-internal", renderer))
        text_preview.extend(_render_text(line, zone_name.cx, y, layout.line_height_mm, cfg, "preview-hole", renderer))
        y += layout.line_height_mm + line_gap

    text_cut.extend(_render_text(number, center_num_x, number_y, number_height, cfg, "cut-internal", renderer))
    text_preview.extend(_render_text(number, center_num_x, number_y, number_height, cfg, "preview-hole", renderer))
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
            f"Zona do nome: {'duas linhas dentro da camisa' if is_compound else 'retangulo guia original'}",
            f"Regra do numero: {'dezena menor, mesma posicao' if len(number) >= 2 else 'unidade aprovada'}",
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
