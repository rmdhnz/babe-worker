import os
from dotenv import load_dotenv

load_dotenv()


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST",)
RABBITMQ_USER = os.getenv("RABBITMQ_USER",)
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
QUEUE_NAME = os.getenv("QUEUE_NAME", "order_queue")