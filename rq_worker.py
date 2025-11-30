# rq_worker.py
import os
from redis import Redis
from rq import Worker, Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
redis_conn = Redis.from_url(REDIS_URL)

if __name__ == "__main__":
    w = Worker([Queue("struk-jobs", connection=redis_conn)])
    w.work(with_scheduler=True)

