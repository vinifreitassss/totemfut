from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


FONT_CANDIDATES = [
    r"C:\\Windows\\Fonts\\STENCIL.TTF",
    r"C:\\Windows\\Fonts\\stencil.ttf",
    r"C:\\Windows\\Fonts\\Stencil.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Stencil.ttf",
]


@dataclass(slots=True)
class FontLineMetrics:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    advance: float

    @property
    def width(self) -> float:
        return max(0.0, self.x_max - self.x_min)

    @property
    def height(self) -> float:
        return max(1.0, self.y_max - self.y_min)


class FontTextRenderer:
    """Renderiza texto como paths SVG a partir de uma fonte stencil instalada.

    O sistema tenta usar STENCIL.TTF do Windows. Se a fonte não existir, o gerador
    principal volta para a fonte modular segura.
    """

    def __init__(self, font_path: str | Path) -> None:
        from fontTools.ttLib import TTFont  # type: ignore

        self.font_path = str(font_path)
        self.font = TTFont(self.font_path)
        self.glyph_set = self.font.getGlyphSet()
        self.units_per_em = float(self.font["head"].unitsPerEm)
        self.hmtx = self.font["hmtx"]
        self.cmap: dict[int, str] = {}
        for table in self.font["cmap"].tables:
            if table.isUnicode():
                self.cmap.update(table.cmap)
        self.letter_spacing_units = self.units_per_em * 0.04
        self.space_units = self.units_per_em * 0.34

    @classmethod
    def try_default(cls) -> "FontTextRenderer | None":
        for raw_path in FONT_CANDIDATES:
            path = Path(raw_path)
            if path.exists():
                try:
                    return cls(path)
                except Exception:
                    continue
        env_path = os.environ.get("TOTEMFUT_STENCIL_FONT")
        if env_path and Path(env_path).exists():
            try:
                return cls(env_path)
            except Exception:
                return None
        return None

    @property
    def font_name(self) -> str:
        return Path(self.font_path).name

    def glyph_name(self, ch: str) -> str | None:
        return self.cmap.get(ord(ch))

    def can_render(self, text: str) -> bool:
        return all(ch == " " or self.glyph_name(ch) is not None for ch in text)

    def glyph_advance(self, glyph_name: str) -> float:
        width, _ = self.hmtx[glyph_name]
        return float(width)

    def glyph_bounds(self, glyph_name: str) -> tuple[float, float, float, float] | None:
        from fontTools.pens.boundsPen import BoundsPen  # type: ignore

        pen = BoundsPen(self.glyph_set)
        self.glyph_set[glyph_name].draw(pen)
        return pen.bounds

    def glyph_path(self, glyph_name: str) -> str:
        from fontTools.pens.svgPathPen import SVGPathPen  # type: ignore

        pen = SVGPathPen(self.glyph_set)
        self.glyph_set[glyph_name].draw(pen)
        return pen.getCommands()

    def line_metrics(self, text: str) -> FontLineMetrics:
        acc = 0.0
        x_min: float | None = None
        y_min: float | None = None
        x_max: float | None = None
        y_max: float | None = None

        for index, ch in enumerate(text):
            if ch == " ":
                acc += self.space_units
                continue
            glyph_name = self.glyph_name(ch)
            if glyph_name is None:
                continue
            bounds = self.glyph_bounds(glyph_name)
            if bounds is not None:
                bx0, by0, bx1, by1 = bounds
                x_min = acc + bx0 if x_min is None else min(x_min, acc + bx0)
                y_min = by0 if y_min is None else min(y_min, by0)
                x_max = acc + bx1 if x_max is None else max(x_max, acc + bx1)
                y_max = by1 if y_max is None else max(y_max, by1)
            acc += self.glyph_advance(glyph_name)
            if index != len(text) - 1:
                acc += self.letter_spacing_units

        if x_min is None or y_min is None or x_max is None or y_max is None:
            return FontLineMetrics(0, 0, acc or self.units_per_em, self.units_per_em, acc)
        return FontLineMetrics(x_min, y_min, x_max, y_max, acc)

    def width_per_height(self, text: str) -> float:
        metrics = self.line_metrics(text)
        return metrics.width / metrics.height

    def render_line(self, text: str, x_center: float, y_top: float, height_mm: float, klass: str) -> list[str]:
        metrics = self.line_metrics(text)
        scale = height_mm / metrics.height
        total_width = metrics.width * scale
        line_left = x_center - total_width / 2.0
        baseline_y = y_top + metrics.y_max * scale
        acc = 0.0
        elements: list[str] = []

        for index, ch in enumerate(text):
            if ch == " ":
                acc += self.space_units
                continue
            glyph_name = self.glyph_name(ch)
            if glyph_name is None:
                continue
            d = self.glyph_path(glyph_name)
            if d:
                x = line_left + (acc - metrics.x_min) * scale
                elements.append(
                    f'<path class="{klass}" d="{d}" transform="translate({x:.3f} {baseline_y:.3f}) scale({scale:.6f} {-scale:.6f})" />'
                )
            acc += self.glyph_advance(glyph_name)
            if index != len(text) - 1:
                acc += self.letter_spacing_units
        return elements
