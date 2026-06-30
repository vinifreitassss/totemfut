# TotemFut

Gerador de SVG/PDF para centro de mesa de futebol personalizado, pensado para MDF 3mm.

O sistema gera:

- silhueta vetorial autoral de jogador com 20 cm de altura visível;
- aba macho de encaixe no corpo;
- base com rasgo calculado pela espessura do MDF + folga;
- nome e número personalizados;
- redução automática do tamanho do nome/número quando passa do limite;
- aumento automático para nomes pequenos até o limite visual definido;
- quebra de linha automática para nomes compostos;
- prévia visual preenchida em preto, mais próxima do produto real;
- camadas de corte em vermelho/azul e gravação opcional em verde.

## V2

A V2 separa melhor produto e corte:

- `totemfut/v2.py`: gerador principal usado pelo app;
- `totemfut/font_renderer.py`: tenta converter uma fonte stencil instalada em curvas SVG;
- `totemfut/generator.py`: motor antigo mantido como fallback/base.

Quando o Windows tiver `STENCIL.TTF`, o texto é convertido em paths SVG, deixando nome e número muito mais próximos de uma fonte esportiva/stencil. Se a fonte não existir, o sistema usa a fonte modular segura da V1.

Também é possível indicar uma fonte manualmente com a variável de ambiente:

```bat
set TOTEMFUT_STENCIL_FONT=C:\Windows\Fonts\STENCIL.TTF
```

## Padrão atual

- Altura visível do jogador: `200 mm`
- MDF: `3 mm`
- Folga do encaixe: `0,25 mm`
- Base: `130 x 50 mm`
- Aba macho: `48 x 12 mm`
- Rasgo da base: `48,25 x 3,25 mm`

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 6060
```

Ou no Windows:

```bat
rodar.bat
```

Abra no navegador:

```txt
http://127.0.0.1:6060
```

## Gerar pelo terminal

```bash
python -m totemfut.cli --nome MIGUEL --numero 10
```

O SVG será salvo em `saidas/MIGUEL_10.svg`.

## Camadas do SVG

- `PREVIEW_PRODUTO`: prévia preenchida em preto e branco.
- `CORTE_CORPO`: contorno externo do jogador.
- `CORTE_INTERNO_TEXTO`: nome, número e furos decorativos da bola.
- `CORTE_BASE`: base e rasgo de encaixe.
- `GRAVACAO_OPCIONAL`: linhas verdes opcionais para leitura de camisa/bola.

Cores padrão:

- vermelho: corte externo;
- azul: corte interno;
- verde: gravação/opcional;
- preto/branco: apenas prévia visual.

## Observações de produção

A V2 ainda precisa ser testada no seu fluxo real de laser/Corel/Inkscape. O objetivo desta etapa foi melhorar proporção, leitura visual e zona de camisa sem perder a lógica paramétrica.
