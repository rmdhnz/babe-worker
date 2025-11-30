import pika
import json

from settings import *

def publish_order(data: dict):
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    payload = json.dumps(data)
    channel.basic_publish(
        exchange='',
        routing_key=QUEUE_NAME,
        body=payload,
        properties=pika.BasicProperties(delivery_mode=2)  # persistent
    )
    connection.close()