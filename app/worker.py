import os
import json
import time
import traceback
from azure.servicebus import ServiceBusClient
from dotenv import load_dotenv

from app.services.image_processor import process_and_save

load_dotenv()

CONNECTION_STR = os.getenv("SERVICE_BUS_CONNECTION")
QUEUE_NAME = os.getenv("QUEUE_NAME")

if not CONNECTION_STR or not QUEUE_NAME:
    raise Exception("Missing SERVICE_BUS_CONNECTION or QUEUE_NAME environment variables")

client = ServiceBusClient.from_connection_string(CONNECTION_STR)

MAX_RETRIES = 3

print("🔥 WORKER FILE LOADED")
def receive_messages():
    print("🚀 Worker started. Listening for messages...")

    with client:
        receiver = client.get_queue_receiver(
            queue_name=QUEUE_NAME,
            max_wait_time=5
        )

        with receiver:
            for message in receiver:
                try:
                    print("\n📩 New message received")

                    # ✅ SAFE decoding
                    body = b"".join(message.body).decode()
                    print("RAW BODY:", body)

                    data = json.loads(body)
                    print("Decoded JSON:", data)

                    filename = data["filename"]
                    url = data["url"]
                    caption = data.get("caption", "")

                    print(f"🛠 Processing: {filename}")

                    process_and_save(filename, url, caption)

                    # ✅ SUCCESS → remove message
                    receiver.complete_message(message)
                    print(f"✅ Completed: {filename}")

                except Exception as e:
                    print("❌ ERROR:", str(e))
                    traceback.print_exc()

                    delivery_count = message.delivery_count

                    if delivery_count > MAX_RETRIES:
                        print("☠️ Dead-lettering message")
                        receiver.dead_letter_message(message)
                    else:
                        print("🔁 Retrying message...")
                        receiver.abandon_message(message)

                    time.sleep(2)


if __name__ == "__main__":
    receive_messages()