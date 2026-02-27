from whatsapp_cloud_api import WhatsAppClient


def main() -> None:
    client = WhatsAppClient(
        access_token="SEU_TOKEN",
        phone_number_id="SEU_PHONE_NUMBER_ID",
        api_version="v20.0",
    )
    try:
        response = client.send_text(
            to="5511999999999",
            body="Teste de envio usando whatsapp-cloud-api-client",
        )
        print(response.model_dump())
    finally:
        client.close()


if __name__ == "__main__":
    main()
