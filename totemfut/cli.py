from __future__ import annotations

import argparse
from pathlib import Path

from .generator import TotemConfig, generate_totem_svg, safe_filename


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gerador SVG para centro de mesa futebol personalizado.")
    parser.add_argument("--nome", required=True, help="Nome do cliente. Ex.: MIGUEL")
    parser.add_argument("--numero", required=True, help="Número da camisa. Ex.: 10")
    parser.add_argument("--altura", type=float, default=200.0, help="Altura visível do jogador em mm. Padrão: 200")
    parser.add_argument("--espessura", type=float, default=3.0, help="Espessura do MDF em mm. Padrão: 3")
    parser.add_argument("--folga", type=float, default=0.25, help="Folga do encaixe em mm. Padrão: 0.25")
    parser.add_argument("--out", default=None, help="Arquivo de saída SVG. Padrão: saidas/NOME_NUMERO.svg")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cfg = TotemConfig(
        visible_height_mm=args.altura,
        material_thickness_mm=args.espessura,
        slot_clearance_mm=args.folga,
    )
    result = generate_totem_svg(args.nome, args.numero, cfg)
    out = Path(args.out) if args.out else Path("saidas") / safe_filename(args.nome, args.numero)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.svg, encoding="utf-8")
    print(f"SVG salvo em: {out}")
    if result.warnings:
        print("Avisos:")
        for warning in result.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
