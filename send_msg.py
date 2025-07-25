import pika
import json

credentials = pika.PlainCredentials("guest", "guest")
parameters = pika.ConnectionParameters(
    host="31.97.106.30", port=5679, credentials=credentials
)

connection = pika.BlockingConnection(parameters)
channel = connection.channel()


channel.queue_declare(queue="whatsapp_hook_queue", durable=True)
channel.queue_declare(queue="whatsapp_message_queue", durable=True)

from_number = "<NOMER DI INSTANCE>"
to_number = "<NOMER BABE>@c.us"

fallback_message = "Testing pesenan yaa"
fallback_payload = {
    "command": "send_message",
    "number": from_number,
    "number_recipient": to_number,
    "message": fallback_message,
}
channel.basic_publish(
    exchange="",
    routing_key="whatsapp_message_queue",
    body=json.dumps(fallback_payload),
    properties=pika.BasicProperties(delivery_mode=2),
)
