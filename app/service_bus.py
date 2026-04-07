from azure.servicebus import ServiceBusClient, ServiceBusMessage
import os
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STR = os.getenv("SERVICE_BUS_CONNECTION")
QUEUE_NAME = os.getenv("QUEUE_NAME")

client = ServiceBusClient.from_connection_string(CONNECTION_STR)

def send_message(message: str):
    with client:
        sender = client.get_queue_sender(queue_name=QUEUE_NAME)
        with sender:
            sender.send_messages(ServiceBusMessage(message))