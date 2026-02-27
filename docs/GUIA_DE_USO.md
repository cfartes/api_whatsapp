# Guia de Uso - whatsapp-cloud-api-client

Este documento explica como configurar e usar a biblioteca `whatsapp-cloud-api-client` em projetos Python.

## 1. Instalacao

```bash
pip install whatsapp-cloud-api-client
```

Para desenvolvimento:

```bash
pip install -e ".[dev]"
```

## 2. Pre-requisitos (Meta WhatsApp Cloud API)

Voce precisa de:

- `access_token` valido da Meta
- `phone_number_id` do numero conectado na WhatsApp Cloud API
- webhook configurado (opcional, mas recomendado para receber eventos)

## 3. Configuracao Basica

### Cliente sincrono

```python
from whatsapp_cloud_api import WhatsAppClient

client = WhatsAppClient(
    access_token="SEU_TOKEN",
    phone_number_id="SEU_PHONE_NUMBER_ID",
    api_version="v20.0",   # opcional
    timeout=20.0,          # opcional
)
```

### Cliente assincrono

```python
from whatsapp_cloud_api import AsyncWhatsAppClient

client = AsyncWhatsAppClient(
    access_token="SEU_TOKEN",
    phone_number_id="SEU_PHONE_NUMBER_ID",
    api_version="v20.0",
    timeout=20.0,
)
```

## 4. Recursos Disponiveis

### 4.1 Enviar texto

```python
response = client.send_text(
    to="5511999999999",
    body="Ola! Mensagem de teste.",
    preview_url=False,            # opcional
    context_message_id=None,      # opcional (resposta a mensagem anterior)
)
print(response.model_dump())
```

### 4.2 Enviar template

```python
response = client.send_template(
    to="5511999999999",
    name="nome_do_template",
    language_code="pt_BR",
    components=[
        {
            "type": "body",
            "parameters": [{"type": "text", "text": "Joao"}],
        }
    ],
)
print(response.model_dump())
```

### 4.3 Enviar midia (por link ou media_id)

```python
# Exemplo com link
response = client.send_media(
    to="5511999999999",
    media_type="image",  # image | document | video | audio | sticker
    link="https://meusite.com/imagem.jpg",
    caption="Legenda opcional",
)
print(response.model_dump())
```

```python
# Exemplo com media_id
response = client.send_media(
    to="5511999999999",
    media_type="document",
    media_id="MEDIA_ID_OBTIDO_ANTES",
    filename="arquivo.pdf",
)
print(response.model_dump())
```

### 4.4 Upload de midia

```python
upload = client.upload_media(file_path="caminho/arquivo.pdf")
print(upload.id)
```

### 4.5 Buscar informacoes de midia

```python
media_info = client.get_media(media_id="MEDIA_ID")
print(media_info.model_dump())
```

### 4.6 Marcar mensagem como lida

```python
result = client.mark_as_read(message_id="wamid.xxxxx")
print(result.success)
```

## 5. Uso Assincrono (async/await)

```python
import asyncio
from whatsapp_cloud_api import AsyncWhatsAppClient


async def main() -> None:
    async with AsyncWhatsAppClient(
        access_token="SEU_TOKEN",
        phone_number_id="SEU_PHONE_NUMBER_ID",
    ) as client:
        response = await client.send_text(
            to="5511999999999",
            body="Mensagem async",
        )
        print(response.model_dump())


asyncio.run(main())
```

## 6. Webhook (validacao)

### 6.1 Validar challenge (GET)

```python
from whatsapp_cloud_api import verify_webhook_challenge

ok, challenge = verify_webhook_challenge(
    mode="subscribe",
    token="TOKEN_RECEBIDO",
    challenge="CHALLENGE_RECEBIDO",
    verify_token="SEU_VERIFY_TOKEN",
)
```

### 6.2 Validar assinatura (POST)

```python
from whatsapp_cloud_api import verify_webhook_signature

is_valid = verify_webhook_signature(
    app_secret="SEU_APP_SECRET",
    raw_body=b'{"entry":[]}',
    x_hub_signature_256="sha256=...",
)
```

## 7. Tratamento de Erros

A biblioteca lanca `WhatsAppAPIError` quando a API retorna erro HTTP ou erro de comunicacao.

```python
from whatsapp_cloud_api import WhatsAppClient, WhatsAppAPIError

client = WhatsAppClient(access_token="...", phone_number_id="...")

try:
    client.send_text(to="5511999999999", body="Teste")
except WhatsAppAPIError as err:
    print(err.message)
    print(err.status_code)
    print(err.code)
    print(err.details)
```

Campos uteis do erro:

- `message`
- `status_code`
- `error_type`
- `code`
- `error_subcode`
- `fbtrace_id`
- `details`

## 8. Retry, Backoff e Rate Limit

A biblioteca possui retry para erros transientes:

- `429`, `500`, `502`, `503`, `504`

Comportamento padrao:

- retry habilitado apenas para `GET`
- `max_retries=3`
- `backoff_factor=0.5`
- `max_backoff=8.0`

Exemplo habilitando retry para `POST` tambem:

```python
client = WhatsAppClient(
    access_token="SEU_TOKEN",
    phone_number_id="SEU_PHONE_NUMBER_ID",
    max_retries=3,
    backoff_factor=0.5,
    max_backoff=8.0,
    retry_methods={"GET", "POST"},
)
```

Se a API retornar cabecalho `Retry-After`, ele e respeitado.

## 9. Tipos de Retorno (Pydantic)

Os metodos retornam modelos tipados:

- `SendMessageResponse`
- `MediaUploadResponse`
- `MediaInfoResponse`
- `MarkAsReadResponse`

Converta para dicionario com:

```python
data = response.model_dump()
```

## 10. Boas Praticas de Producao

- Armazene `access_token` em variavel de ambiente/secrets manager.
- Nao logue token em texto puro.
- Use timeout configurado para evitar requests presas.
- Monitore erros `429` para ajuste de throughput.
- Use webhook com validacao de assinatura sempre.

## 11. Exemplo com variaveis de ambiente

```python
import os
from whatsapp_cloud_api import WhatsAppClient

client = WhatsAppClient(
    access_token=os.environ["WHATSAPP_ACCESS_TOKEN"],
    phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
)
```

## 12. Fluxo recomendado para usar em app

1. Inicialize o client na camada de servico.
2. Implemente funcao de envio (texto/template/midia).
3. Implemente endpoint webhook (GET + POST).
4. Trate `WhatsAppAPIError` com logs estruturados.
5. Adicione observabilidade para latencia e falhas.

