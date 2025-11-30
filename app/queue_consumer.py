import pika
import time
import os
from order_worker import process_order
import json

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq_order")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "order_queue")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))


def connect_rabbitmq():
    """Create RabbitMQ connection with retry logic."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

    for attempt in range(20):  # retry 20x
        try:
            print(f"[Worker] Connecting to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    port=RABBITMQ_PORT,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=600
                )
            )
            print("[Worker] Connected to RabbitMQ")
            return connection
        except Exception as e:
            print(f"[Worker] RabbitMQ not ready: {e}. Retry {attempt + 1}/20...")
            time.sleep(3)

    raise Exception("[Worker] ERROR: Failed to connect to RabbitMQ after 20 retries")


def callback(ch, method, properties, body):
    """Callback saat menerima pesan dari queue"""
    try:
        data = json.loads(body)
        print(f"[Worker] Received order: {data}")

        result = process_order(data)

        print(f"[Worker] Order processed result: {result}")

        # ack message setelah sukses
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("[Worker] ACK sent")

    except Exception as e:
        print(f"[Worker] ERROR processing message: {e}")
        # jangan ACK supaya pesan bisa retry
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        print("[Worker] NACK sent → requeue message")


def start_consumer():
    connection = connect_rabbitmq()
    channel = connection.channel()

    channel.queue_declare(
            queue="order_queue",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": "order_dlq"
            }
        )
    channel.queue_declare(queue="order_dlq", durable=True)

    print(f"[Worker] Listening for messages on '{RABBITMQ_QUEUE}' ...")
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("[Worker] STOP signal received — closing connection.")
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    print("[Worker] Starting Queue Consumer...")
    start_consumer()
