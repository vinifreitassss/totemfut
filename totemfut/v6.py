from __future__ import annotations

from . import v5
from .template_loader import Rect

GeneratedTotem = v5.GeneratedTotem
TotemConfig = v5.TotemConfig
safe_filename = v5.safe_filename


def _compound_zone(guide: Rect) -> Rect:
    # Nome composto deve caber dentro do retangulo-guia original.
    return Rect(
        guide.x + guide.width * 0.03,
        guide.y + guide.height * 0.04,
        guide.width * 0.94,
        guide.height * 0.92,
    )


def _compound_name_layout(name: str, guide: Rect, cfg: TotemConfig, renderer=None):
    words = name.split()
    if len(words) <= 1:
        layout = v5._single_name_layout(name, guide, cfg, renderer)
        return layout, guide

    zone = _compound_zone(guide)
    lines = v5._break_compound(words, cfg, renderer)
    line_gap = zone.height * 0.06
    max_line_height = (zone.height - line_gap) / 2.0
    line_height, warnings = v5._fit_height_strict(
        lines,
        desired=max_line_height * 0.92,
        max_width=zone.width,
        max_height=max_line_height,
        cfg=cfg,
        renderer=renderer,
    )
    return v5.old.TextLayout(lines, line_height, warnings), zone


v5._compound_zone = _compound_zone
v5._compound_name_layout = _compound_name_layout


def generate_totem_svg(nome: str, numero: str, cfg: TotemConfig | None = None) -> GeneratedTotem:
    return v5.generate_totem_svg(nome, numero, cfg)
