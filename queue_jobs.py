# queue_jobs.py
import os, json, time
from redis import Redis
from rq import Queue, Retry
from typing import Dict, Any
from convert_rawcart_to_ord import StrukMaker

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
redis_conn = Redis.from_url(REDIS_URL)
q = Queue("struk-jobs", connection=redis_conn, default_timeout=600)  # 10 menit

agent = StrukMaker()

def process_order_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker entrypoint: proses berat — insert items/combo, payment, update status, log, forward WA.
    Return dict summary; lempar exception kalau gagal supaya RQ retry otomatis.
    """
    # Panggil method agent yang existing tapi versi "lanjutan".
    # Kita ekspos method baru agent.finish_order(payload) (lihat bagian 4).
    return agent.finish_order(payload)

def enqueue_order_job(payload: Dict[str, Any], idem_key: str):
    # Cegah duplikat selama 5 menit: gunakan Redis SETNX (opsional)
    lock_key = f"idem:{idem_key}"
    if redis_conn.set(lock_key, "1", nx=True, ex=300) is None:
        # Sudah ada job identik dalam 5 menit terakhir
        return {"already_enqueued": True}

    job = q.enqueue(
        process_order_job,
        payload,
        job_id=f"order:{idem_key}",  # supaya tidak dobel
        retry=Retry(max=5, interval=[10, 20, 40, 80, 160])  # backoff sederhana
    )
    return {"job_id": job.id, "enqueued": True}
