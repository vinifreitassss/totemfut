# TotemFut

Gerador de SVG/PDF para centro de mesa de futebol personalizado, pensado para MDF 3mm.

O sistema gera:

- silhueta vetorial autoral de jogador com 20 cm de altura visível;
- aba macho de encaixe no corpo;
- base com rasgo calculado pela espessura do MDF + folga;
- nome e número em fonte vetorial própria, sem depender de fonte instalada;
- redução automática do tamanho do nome/número quando passa do limite;
- aumento automático para nomes pequenos até o limite visual definido;
- quebra de linha automática para nomes compostos;
- tratamento de caracteres perigosos como `0, 4, 6, 8, 9, A, B, D, O, P, Q, R`.

## Padrão da V1

- Altura visível do jogador: `200 mm`
- MDF: `3 mm`
- Folga do encaixe: `0,25 mm`
- Base: `130 x 50 mm`
- Aba macho: `50 x 12 mm`
- Rasgo da base: `50,25 x 3,25 mm`

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 6060
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

- `CORTE_CORPO`: contorno externo do jogador.
- `CORTE_INTERNO_TEXTO`: nome, número e furos decorativos da bola.
- `CORTE_BASE`: base e rasgo de encaixe.
- `engrave`: linhas verdes opcionais para gravação, como contorno da bola.

Cores padrão:

- vermelho: corte externo;
- azul: corte interno;
- verde: gravação/opcional.

## Observações de produção

A fonte da V1 se chama `TotemStencil`. Ela é uma fonte modular vetorial, feita com pequenos cortes separados por pontes de MDF. Isso evita o problema clássico de miolos caírem em letras e números vazados.

A estética ainda pode evoluir para uma fonte mais elegante, com serifas e pontes desenhadas manualmente. A base do sistema já está pronta para trocar a biblioteca de letras sem mudar a lógica principal.
