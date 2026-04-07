import os
import json
import time
from azure.servicebus import ServiceBusClient
from dotenv import load_dotenv

from app.services.image_processor import process_and_save

load_dotenv()

CONNECTION_STR = os.getenv("SERVICE_BUS_CONNECTION")
QUEUE_NAME = os.getenv("QUEUE_NAME")

client = ServiceBusClient.from_connection_string(CONNECTION_STR)

MAX_RETRIES = 3

def receive_messages():
    print("Listening for messages...")

    with client:
        receiver = client.get_queue_receiver(queue_name=QUEUE_NAME)

        with receiver:
            for message in receiver:
                try:
                    data = json.loads(str(message))

                    filename = data["filename"]
                    url = data["url"]

                    print("Processing:", filename)

                    process_and_save(filename, url)

                    # SUCCESS → remove from queue
                    receiver.complete_message(message)

                except Exception as e:
                    print("ERROR:", e)

                    delivery_count = message.delivery_count

                    # Dead-letter after too many retries
                    if delivery_count > MAX_RETRIES:
                        print("Dead-lettering message:", message)
                        receiver.dead_letter_message(message)
                    else:
                        print("Retrying message...")
                        receiver.abandon_message(message)

                    time.sleep(2)


if __name__ == "__main__":
    receive_messages()