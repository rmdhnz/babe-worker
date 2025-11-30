import pika, json
from settings import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS

credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
channel = connection.channel()
channel.queue_declare(queue="order_dlq", durable=True)

def callback(ch, method, properties, body):
    try : 
      data = json.loads(body)
      print("🚨 ORDER MASUK DLQ:", data.get("order_no"))
      ch.basic_ack(delivery_tag=method.delivery_tag)
    except KeyboardInterrupt:
       print("Thanks") 

print("🔥 DLQ Monitor aktif...")
channel.basic_consume("order_dlq", callback)
channel.start_consuming()
