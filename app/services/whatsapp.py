import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

_twilio: Client | None = None


def _get_client() -> Client:
    global _twilio
    if _twilio is None:
        _twilio = Client(os.environ["TWILIO_SID"], os.environ["TWILIO_AUTH"])
    return _twilio


def send_message(to_phone: str, body: str) -> None:
    client = _get_client()
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    to = f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone
    client.messages.create(body=body, from_=from_number, to=to)
