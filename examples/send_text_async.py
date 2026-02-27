import asyncio

from whatsapp_cloud_api import AsyncWhatsAppClient


async def main() -> None:
    async with AsyncWhatsAppClient(
        access_token="SEU_TOKEN",
        phone_number_id="SEU_PHONE_NUMBER_ID",
        api_version="v20.0",
    ) as client:
        response = await client.send_text(
            to="5511999999999",
            body="Teste async de envio usando whatsapp-cloud-api-client",
        )
        print(response.model_dump())


if __name__ == "__main__":
    asyncio.run(main())
