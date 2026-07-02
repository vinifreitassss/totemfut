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

ACCENT_TILDE = set("ÃÕ")


def _normalize_display_name(raw: str) -> str:
    """Mantém letras acentuadas para fontes que suportam português."""
    text = (raw or "").strip().upper()
    kept: list[str] = []
    for ch in text:
        category = unicodedata.category(ch)
        if ch.isdigit() or ch in " -" or category.startswith("L"):
            kept.append(ch)
    return re.sub(r"\s+", " ", "".join(kept)).strip()


def _plain(text: str) -> str:
    return base.normalize_text(text)


def _width_per_height(text: str, cfg: TotemConfig, renderer=None) -> float:
    if renderer is not None:
        try:
            return renderer.width_per_height(text)
        except Exception:
            pass
    return base.text_units(_plain(text), cfg) / 7.0


def _fit_height_strict(lines: list[str], desired: float, max_width: float, max_height: float, cfg: TotemConfig, renderer=None) -> tuple[float, list[str]]:
    """Encaixa sem estourar limite.

    Diferente das versões antigas, aqui o mínimo não força a peça a sair da área.
    Se ficar pequeno demais, avisa, mas respeita o limite visual.
    """
    warnings: list[str] = []
    ratio = max((_width_per_height(line, cfg, renderer) for line in lines), default=0.0)
    height = min(desired, max_height)
    if ratio > 0:
        height = min(height, max_width / ratio)
    if height < 4.0:
        warnings.append("Texto ficou abaixo do ideal; revise visualmente ou abrevie.")
    return height, warnings


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


def _single_name_layout(name: str, guide: Rect, cfg: TotemConfig, renderer=None) -> old.TextLayout:
    # REGRA 1: nome simples usa exatamente o retângulo original.
    # Ele só reduz se o texto realmente não couber na largura.
    line_height, warnings = _fit_height_strict(
        [name],
        desired=guide.height * 0.92,
        max_width=guide.width * 0.94,
        max_height=guide.height * 0.92,
        cfg=cfg,
        renderer=renderer,
    )
    return old.TextLayout([name], line_height, warnings)


def _compound_zone(guide: Rect) -> Rect:
    # REGRA 2: nome composto usa a mesma largura do retângulo original.
    # Só ganha altura para caber duas linhas dentro do corpo/camisa.
    return Rect(
        guide.x + guide.width * 0.02,
        guide.y - guide.height * 0.28,
        guide.width * 0.96,
        guide.height * 2.12,
    )


def _compound_name_layout(name: str, guide: Rect, cfg: TotemConfig, renderer=None) -> tuple[old.TextLayout, Rect]:
    words = name.split()
    if len(words) <= 1:
        layout = _single_name_layout(name, guide, cfg, renderer)
        return layout, guide

    zone = _compound_zone(guide)
    lines = _break_compound(words, cfg, renderer)
    line_gap = zone.height * 0.08
    max_line_height = (zone.height - line_gap) / 2.0
    line_height, warnings = _fit_height_strict(
        lines,
        desired=min(guide.height * 0.86, max_line_height),
        max_width=zone.width * 0.88,
        max_height=max_line_height,
        cfg=cfg,
        renderer=renderer,
    )
    return old.TextLayout(lines, line_height, warnings), zone


def _number_box_from_old_position(guide: Rect, cfg: TotemConfig, digits: int) -> tuple[float, float, float, float]:
    # REGRA 3: a posição aprovada do número é a antiga.
    # Para dezena, muda só a escala; o topo antigo permanece como âncora.
    zone_x = guide.x + guide.width * 0.18
    zone_y = guide.y2 + max(3.0, guide.height * 0.30)
    zone_w = guide.width * 0.64
    zone_h = cfg.visible_height_mm * 0.22
    single_height = 31.0
    top_anchor = zone_y + (zone_h - single_height) / 2.0
    center_x = zone_x + zone_w / 2.0

    if digits <= 1:
        desired_height = single_height
        max_width = zone_w * 0.80
    else:
        desired_height = 22.8
        max_width = zone_w * 1.02
    return center_x, top_anchor, desired_height, max_width


def _accent_marks_for_fallback(text: str, x_center: float, y_top: float, height: float, cfg: TotemConfig, klass: str) -> list[str]:
    if not any(ch in ACCENT_TILDE for ch in text.upper()):
        return []

    plain = _plain(text)
    if not plain:
        return []

    pitch = height / 7.0
    width = base.estimate_text_width(plain, height, cfg)
    x_cursor = x_center - width / 2.0
    elements: list[str] = []
    accent_class = "cut-accent" if klass == "cut-internal" else "preview-accent"

    for idx, ch in enumerate(text.upper()):
        plain_ch = _plain(ch)
        if not plain_ch:
            continue
        if plain_ch == " ":
            advance = cfg.space_units * pitch
        else:
            advance = 5.0 * pitch
            if ch in ACCENT_TILDE:
                cx = x_cursor + 2.5 * pitch
                y = y_top - 0.80 * pitch
                d = (
                    f"M {base.fmt(cx - 1.65 * pitch)} {base.fmt(y)} "
                    f"C {base.fmt(cx - 0.85 * pitch)} {base.fmt(y - 0.70 * pitch)} "
                    f"{base.fmt(cx + 0.85 * pitch)} {base.fmt(y + 0.70 * pitch)} "
                    f"{base.fmt(cx + 1.65 * pitch)} {base.fmt(y)}"
                )
                elements.append(f'<path class="{accent_class}" d="{d}" />')
        x_cursor += advance
        if idx != len(text) - 1:
            x_cursor += cfg.char_gap_units * pitch
    return elements


def _render_text(text: str, x: float, y: float, height: float, cfg: TotemConfig, klass: str, renderer=None) -> list[str]:
    if renderer is not None:
        try:
            return renderer.render_line(text, x, y, height, klass)
        except Exception:
            pass
    items = base.render_grid_text(_plain(text), x, y, height, cfg, klass)
    items.extend(_accent_marks_for_fallback(text, x, y, height, cfg, klass))
    return items


def generate_totem_svg(nome: str, numero: str, cfg: TotemConfig | None = None) -> GeneratedTotem:
    cfg = cfg or TotemConfig()

    display_name = _normalize_display_name(nome)
    fallback_name = _plain(nome)
    number = re.sub(r"[^0-9]", "", _plain(numero))[:2] or "10"
    renderer = old._renderer(cfg, display_name, number)
    name = display_name if renderer is not None else display_name or fallback_name

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
    if is_compound:
        layout, name_zone = _compound_name_layout(name, guide, cfg, renderer)
    else:
        layout = _single_name_layout(name, guide, cfg, renderer)
        name_zone = guide

    center_num_x, number_y, desired_number_height, max_number_width = _number_box_from_old_position(guide, cfg, len(number))
    number_height, number_warnings = _fit_height_strict(
        [number],
        desired=desired_number_height,
        max_width=max_number_width,
        max_height=desired_number_height,
        cfg=cfg,
        renderer=renderer,
    )

    warnings: list[str] = []
    if renderer is not None:
        warnings.append(f"Texto renderizado em curvas pela fonte instalada: {renderer.font_name}.")
    else:
        warnings.append("Fonte STENCIL.TTF sem suporte completo ou não encontrada; usei a fonte modular segura com til manual quando necessário.")
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

    line_gap = name_zone.height * 0.08 if len(layout.lines) > 1 else 0.0
    total_name_h = layout.line_height_mm * len(layout.lines) + line_gap * (len(layout.lines) - 1)
    y = name_zone.y + (name_zone.height - total_name_h) / 2.0
    for line in layout.lines:
        text_cut.extend(_render_text(line, name_zone.cx, y, layout.line_height_mm, cfg, "cut-internal", renderer))
        text_preview.extend(_render_text(line, name_zone.cx, y, layout.line_height_mm, cfg, "preview-hole", renderer))
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
      .cut-accent { fill: none; stroke: #0000ff; stroke-width: 0.12; stroke-linecap: round; vector-effect: non-scaling-stroke; }
      .preview-fill { fill: #111111; stroke: none; fill-rule: evenodd; }
      .preview-hole { fill: #ffffff; stroke: none; fill-rule: evenodd; }
      .preview-accent { fill: none; stroke: #ffffff; stroke-width: 0.9; stroke-linecap: round; vector-effect: non-scaling-stroke; }
    </style>
    """
    metadata = "\n".join(
        f"    <!-- {escape(line)} -->" for line in [
            f"Nome normalizado: {name}",
            f"Numero normalizado: {number}",
            f"Altura visivel do corpo: {cfg.visible_height_mm} mm",
            f"Regra nome: {'composto em duas linhas dentro da largura do retangulo' if is_compound else 'simples no retangulo original'}",
            f"Regra numero: {'dezena menor com posicao antiga' if len(number) >= 2 else 'unidade antiga'}",
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
