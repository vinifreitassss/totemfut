from __future__ import annotations

from html import escape

from fastapi import FastAPI, Query, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from totemfut import TotemConfig, generate_totem_svg, safe_filename

app = FastAPI(title="TotemFut", version="0.1.0")


def make_cfg(
    altura: float,
    espessura: float,
    folga: float,
    base_largura: float,
    base_profundidade: float,
) -> TotemConfig:
    return TotemConfig(
        visible_height_mm=altura,
        material_thickness_mm=espessura,
        slot_clearance_mm=folga,
        base_width_mm=base_largura,
        base_depth_mm=base_profundidade,
    )


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TotemFut</title>
  <style>
    body { font-family: system-ui, Arial, sans-serif; max-width: 980px; margin: 24px auto; padding: 0 16px; background: #f7f7f7; color: #161616; }
    .card { background: #fff; border: 1px solid #ddd; border-radius: 14px; padding: 18px; box-shadow: 0 4px 18px rgba(0,0,0,.06); }
    label { display: block; font-weight: 700; margin-top: 12px; }
    input { width: 100%; box-sizing: border-box; padding: 11px; border: 1px solid #bbb; border-radius: 10px; font-size: 16px; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    button, a.button { display: inline-block; border: 0; border-radius: 10px; background: #111; color: white; padding: 12px 16px; font-weight: 700; text-decoration: none; cursor: pointer; margin-top: 16px; }
    a.button.secondary { background: #2d4d8f; }
    #preview { margin-top: 18px; background: white; border: 1px dashed #aaa; border-radius: 12px; padding: 12px; overflow: auto; }
    #preview svg { max-height: 620px; width: 100%; height: auto; }
    .small { color: #555; font-size: 14px; line-height: 1.35; }
    .warn { background: #fff6d6; border: 1px solid #e3c76a; padding: 10px; border-radius: 10px; margin-top: 12px; }
    @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="card">
    <h1>TotemFut</h1>
    <p class="small">Gerador de SVG para centro de mesa futebol em MDF 3mm. Vermelho = corte externo, azul = corte interno, verde = gravação opcional.</p>

    <label>Nome</label>
    <input id="nome" value="MIGUEL" maxlength="32">

    <label>Número</label>
    <input id="numero" value="10" maxlength="2" inputmode="numeric">

    <div class="grid">
      <div>
        <label>Altura visível (mm)</label>
        <input id="altura" type="number" value="200" step="1">
      </div>
      <div>
        <label>Espessura MDF (mm)</label>
        <input id="espessura" type="number" value="3" step="0.1">
      </div>
      <div>
        <label>Folga do encaixe (mm)</label>
        <input id="folga" type="number" value="0.25" step="0.05">
      </div>
      <div>
        <label>Largura da base (mm)</label>
        <input id="base_largura" type="number" value="130" step="1">
      </div>
      <div>
        <label>Profundidade da base (mm)</label>
        <input id="base_profundidade" type="number" value="50" step="1">
      </div>
    </div>

    <button onclick="preview()">Gerar prévia</button>
    <a id="downloadSvg" class="button secondary" href="#">Baixar SVG</a>
    <a id="downloadPdf" class="button secondary" href="#">Baixar PDF</a>
    <div id="messages"></div>
  </div>
  <div id="preview"></div>

<script>
function params() {
  const p = new URLSearchParams();
  for (const id of ['nome', 'numero', 'altura', 'espessura', 'folga', 'base_largura', 'base_profundidade']) {
    p.set(id, document.getElementById(id).value);
  }
  return p;
}
async function preview() {
  const p = params();
  document.getElementById('downloadSvg').href = '/svg?' + p.toString();
  document.getElementById('downloadPdf').href = '/pdf?' + p.toString();
  const response = await fetch('/svg?' + p.toString());
  const svg = await response.text();
  document.getElementById('preview').innerHTML = svg;
  const meta = await fetch('/meta?' + p.toString()).then(r => r.json());
  const warnings = meta.warnings || [];
  document.getElementById('messages').innerHTML = warnings.length
    ? '<div class="warn"><b>Avisos:</b><br>' + warnings.map(w => '• ' + w).join('<br>') + '</div>'
    : '';
}
preview();
</script>
</body>
</html>
"""


@app.get("/svg")
def svg(
    nome: str = Query("MIGUEL"),
    numero: str = Query("10"),
    altura: float = Query(200.0, ge=120.0, le=350.0),
    espessura: float = Query(3.0, ge=1.5, le=10.0),
    folga: float = Query(0.25, ge=0.0, le=1.0),
    base_largura: float = Query(130.0, ge=80.0, le=240.0),
    base_profundidade: float = Query(50.0, ge=30.0, le=120.0),
) -> Response:
    cfg = make_cfg(altura, espessura, folga, base_largura, base_profundidade)
    result = generate_totem_svg(nome, numero, cfg)
    filename = safe_filename(nome, numero)
    return Response(
        content=result.svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="{escape(filename)}"'},
    )


@app.get("/meta")
def meta(
    nome: str = Query("MIGUEL"),
    numero: str = Query("10"),
    altura: float = Query(200.0),
    espessura: float = Query(3.0),
    folga: float = Query(0.25),
    base_largura: float = Query(130.0),
    base_profundidade: float = Query(50.0),
) -> dict[str, object]:
    cfg = make_cfg(altura, espessura, folga, base_largura, base_profundidade)
    result = generate_totem_svg(nome, numero, cfg)
    return {
        "nome": result.normalized_name,
        "numero": result.normalized_number,
        "linhas_nome": result.name_lines,
        "warnings": result.warnings,
    }


@app.get("/pdf")
def pdf(
    nome: str = Query("MIGUEL"),
    numero: str = Query("10"),
    altura: float = Query(200.0, ge=120.0, le=350.0),
    espessura: float = Query(3.0, ge=1.5, le=10.0),
    folga: float = Query(0.25, ge=0.0, le=1.0),
    base_largura: float = Query(130.0, ge=80.0, le=240.0),
    base_profundidade: float = Query(50.0, ge=30.0, le=120.0),
):
    cfg = make_cfg(altura, espessura, folga, base_largura, base_profundidade)
    result = generate_totem_svg(nome, numero, cfg)
    try:
        import cairosvg  # type: ignore
    except Exception:
        return PlainTextResponse(
            "PDF indisponível. Instale a dependência opcional com: pip install cairosvg",
            status_code=501,
        )
    pdf_bytes = cairosvg.svg2pdf(bytestring=result.svg.encode("utf-8"))
    filename = safe_filename(nome, numero, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{escape(filename)}"'},
    )
