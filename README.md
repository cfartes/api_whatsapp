# WhatsApp Cloud API Client (Python)

Biblioteca Python para integracao com a API Oficial do WhatsApp (Cloud API), com foco em simplicidade de uso em apps.

## Instalacao

```bash
pip install whatsapp-cloud-api-client
```

Para desenvolvimento local:

```bash
pip install -e ".[dev]"
```

## Uso rapido (sync)

```python
from whatsapp_cloud_api import WhatsAppClient

client = WhatsAppClient(
    access_token="SEU_TOKEN",
    phone_number_id="SEU_PHONE_NUMBER_ID",
)

resp = client.send_text(
    to="5511999999999",
    body="Ola! Mensagem enviada via Cloud API.",
)
print(resp.model_dump())
```

## Uso rapido (async)

```python
import asyncio
from whatsapp_cloud_api import AsyncWhatsAppClient


async def main() -> None:
    async with AsyncWhatsAppClient(
        access_token="SEU_TOKEN",
        phone_number_id="SEU_PHONE_NUMBER_ID",
    ) as client:
        resp = await client.send_text(
            to="5511999999999",
            body="Mensagem async",
        )
        print(resp.model_dump())


asyncio.run(main())
```

## Modelos tipados (Pydantic)

Os metodos retornam modelos Pydantic:

- `SendMessageResponse`
- `MediaUploadResponse`
- `MediaInfoResponse`
- `MarkAsReadResponse`

## Retry, backoff e rate limit

O cliente possui retry configuravel para erros transientes (`429`, `500`, `502`, `503`, `504`).

Por padrao, retry roda apenas para `GET` para evitar duplicidade em envio de mensagem (`POST`).

```python
from whatsapp_cloud_api import WhatsAppClient

client = WhatsAppClient(
    access_token="SEU_TOKEN",
    phone_number_id="SEU_PHONE_NUMBER_ID",
    max_retries=3,
    backoff_factor=0.5,
    max_backoff=8.0,
    retry_methods={"GET", "POST"},  # habilite POST se quiser retry em envio
)
```

Se a API retornar `Retry-After`, esse valor sera respeitado.

## Funcionalidades implementadas

- Envio de mensagem de texto
- Envio de mensagem template
- Envio de midia por `media_id` ou `link` (imagem, documento, video, audio, sticker)
- Upload de midia
- Marcar mensagem como lida
- Busca de informacoes de midia
- Validacao de assinatura de webhook (`X-Hub-Signature-256`)
- Cliente sincrono e assincrono

## Exemplo com Flask (webhook)

```python
from flask import Flask, request, jsonify
from whatsapp_cloud_api import verify_webhook_signature, verify_webhook_challenge

app = Flask(__name__)
APP_SECRET = "SEU_APP_SECRET"
VERIFY_TOKEN = "SEU_VERIFY_TOKEN"


@app.get("/webhook")
def webhook_verify():
    ok, challenge = verify_webhook_challenge(
        mode=request.args.get("hub.mode"),
        token=request.args.get("hub.verify_token"),
        challenge=request.args.get("hub.challenge"),
        verify_token=VERIFY_TOKEN,
    )
    if not ok:
        return "forbidden", 403
    return challenge, 200


@app.post("/webhook")
def webhook_receive():
    if not verify_webhook_signature(
        app_secret=APP_SECRET,
        raw_body=request.get_data(),
        x_hub_signature_256=request.headers.get("X-Hub-Signature-256", ""),
    ):
        return "invalid signature", 401

    data = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "received": bool(data)}), 200
```

## Rodar testes

```bash
pytest
```

## CI e publicacao

- CI: `.github/workflows/ci.yml`
- Criacao de tag/release: `.github/workflows/release.yml`
- Publicacao PyPI: `.github/workflows/publish.yml`

Fluxo recomendado:

1. Execute o workflow `Create Release` e informe a tag (ex: `v0.2.0`).
2. O release publicado dispara `Publish to PyPI`.
3. Configure Trusted Publisher no PyPI para este repositorio (OIDC), sem token manual.

Opcional: se preferir token, adapte o workflow para usar `PYPI_API_TOKEN`.

## Licenca

MIT
