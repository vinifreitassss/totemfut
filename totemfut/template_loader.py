from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
COMMANDS = set("MmZzLlHhVvCcSsQqTtAa")
PARAMS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
TOKEN_RE = re.compile(r"[MmZzLlHhVvCcSsQqTtAa]|[+-]?(?:\d*\.\d+|\d+\.?)(?:[eE][+-]?\d+)?")


@dataclass(slots=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.height / 2.0

    def union(self, other: "Rect") -> "Rect":
        x1 = min(self.x, other.x)
        y1 = min(self.y, other.y)
        x2 = max(self.x2, other.x2)
        y2 = max(self.y2, other.y2)
        return Rect(x1, y1, x2 - x1, y2 - y1)

    def transformed(self, tx: float, ty: float, scale: float, origin: "Rect") -> "Rect":
        return Rect(
            tx + (self.x - origin.x) * scale,
            ty + (self.y - origin.y) * scale,
            self.width * scale,
            self.height * scale,
        )


@dataclass(slots=True)
class PathShape:
    d: str
    bbox: Rect


@dataclass(slots=True)
class PlayerTemplate:
    outer: PathShape
    internal_paths: list[PathShape]
    bbox: Rect
    name_zone: Rect


@dataclass(slots=True)
class BaseTemplate:
    outer: Rect
    slot: Rect


def _asset_path(filename: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / "assets" / filename


def _tag_name(element: ET.Element) -> str:
    return element.tag.split("}")[-1]


def _tokens(d: str) -> list[str]:
    return TOKEN_RE.findall(d.replace(",", " "))


def _is_cmd(token: str) -> bool:
    return len(token) == 1 and token in COMMANDS


def _rect_from_points(points: list[tuple[float, float]]) -> Rect:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def path_bbox(d: str) -> Rect:
    """Aproxima a bbox de paths do CorelDRAW usando pontos finais e controles.

    Para escala e posicionamento isto é suficiente e evita uma dependência pesada.
    """
    toks = _tokens(d)
    i = 0
    cmd: str | None = None
    x = y = 0.0
    sx = sy = 0.0
    points: list[tuple[float, float]] = []

    while i < len(toks):
        if _is_cmd(toks[i]):
            cmd = toks[i]
            i += 1
        if cmd is None:
            break

        upper = cmd.upper()
        relative = cmd.islower()
        if upper == "Z":
            x, y = sx, sy
            points.append((x, y))
            cmd = None
            continue

        param_count = PARAMS[upper]
        while i < len(toks) and not _is_cmd(toks[i]):
            if i + param_count > len(toks):
                break
            values: list[float] = []
            for _ in range(param_count):
                if i >= len(toks) or _is_cmd(toks[i]):
                    return _rect_from_points(points or [(0.0, 0.0)])
                values.append(float(toks[i]))
                i += 1

            if upper == "M":
                nx, ny = values[0], values[1]
                if relative:
                    nx += x
                    ny += y
                x, y = nx, ny
                sx, sy = x, y
                points.append((x, y))
                cmd = "l" if relative else "L"
                upper = "L"
                relative = cmd.islower()
                param_count = 2
            elif upper == "L":
                nx, ny = values[0], values[1]
                if relative:
                    nx += x
                    ny += y
                x, y = nx, ny
                points.append((x, y))
            elif upper == "H":
                x = values[0] + x if relative else values[0]
                points.append((x, y))
            elif upper == "V":
                y = values[0] + y if relative else values[0]
                points.append((x, y))
            elif upper == "C":
                coords: list[tuple[float, float]] = []
                for j in range(0, 6, 2):
                    px, py = values[j], values[j + 1]
                    if relative:
                        px += x
                        py += y
                    coords.append((px, py))
                points.extend(coords)
                x, y = coords[-1]
            elif upper in {"S", "Q"}:
                coords = []
                for j in range(0, len(values), 2):
                    px, py = values[j], values[j + 1]
                    if relative:
                        px += x
                        py += y
                    coords.append((px, py))
                points.extend(coords)
                x, y = coords[-1]
            elif upper == "T":
                nx, ny = values[0], values[1]
                if relative:
                    nx += x
                    ny += y
                x, y = nx, ny
                points.append((x, y))
            elif upper == "A":
                rx, ry, _rot, _large, _sweep, ex, ey = values
                if relative:
                    ex += x
                    ey += y
                points.extend([(x - rx, y - ry), (x + rx, y + ry), (ex - rx, ey - ry), (ex + rx, ey + ry), (ex, ey)])
                x, y = ex, ey

    return _rect_from_points(points or [(0.0, 0.0)])


def _rect_from_svg(element: ET.Element) -> Rect:
    return Rect(
        float(element.attrib.get("x", 0.0)),
        float(element.attrib.get("y", 0.0)),
        float(element.attrib.get("width", 0.0)),
        float(element.attrib.get("height", 0.0)),
    )


@lru_cache(maxsize=1)
def load_player_template() -> PlayerTemplate:
    tree = ET.parse(_asset_path("CORPO.svg"))
    root = tree.getroot()

    paths: list[PathShape] = []
    rects: list[Rect] = []
    for element in root.iter():
        tag = _tag_name(element)
        if tag == "path" and element.attrib.get("d"):
            d = element.attrib["d"]
            paths.append(PathShape(d=d, bbox=path_bbox(d)))
        elif tag == "rect":
            rects.append(_rect_from_svg(element))

    if not paths:
        raise RuntimeError("assets/CORPO.svg não contém paths de corte.")

    paths.sort(key=lambda shape: shape.bbox.width * shape.bbox.height, reverse=True)
    outer = paths[0]
    internal = paths[1:]
    bbox = outer.bbox
    for shape in internal:
        bbox = bbox.union(shape.bbox)

    if rects:
        name_zone = max(rects, key=lambda rect: rect.width * rect.height)
    else:
        name_zone = Rect(
            bbox.x + bbox.width * 0.32,
            bbox.y + bbox.height * 0.24,
            bbox.width * 0.36,
            bbox.height * 0.07,
        )

    return PlayerTemplate(outer=outer, internal_paths=internal, bbox=bbox, name_zone=name_zone)


@lru_cache(maxsize=1)
def load_base_template() -> BaseTemplate:
    tree = ET.parse(_asset_path("SVG_BASE.svg"))
    root = tree.getroot()
    rects = [_rect_from_svg(element) for element in root.iter() if _tag_name(element) == "rect"]
    if len(rects) < 2:
        raise RuntimeError("assets/SVG_BASE.svg precisa ter retângulo externo e rasgo.")
    rects.sort(key=lambda rect: rect.width * rect.height, reverse=True)
    return BaseTemplate(outer=rects[0], slot=rects[1])
