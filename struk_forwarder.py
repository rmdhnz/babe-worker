import json
import pika
import time
import requests
from datetime import datetime, timedelta
from modules.maps_utility import estimasi_tiba
from modules.models_sqlalchemy import StrukLog
from modules.sqlalchemy_setup import get_db_session

connection = None
channel = None


def get_channel():
    """Cek koneksi RabbitMQ, kalau mati otomatis reconnect"""
    global connection, channel

    try:
        if connection is None or connection.is_closed:
            reconnect()

        if channel is None or channel.is_closed:
            channel = connection.channel()
            channel.queue_declare(queue="whatsapp_hook_queue", durable=True)
            channel.queue_declare(queue="whatsapp_message_queue", durable=True)

    except Exception as e:
        print(f"[RabbitMQ] Reconnect gagal: {str(e)}")
        reconnect()

    return channel


def reconnect():
    """Buat ulang koneksi RabbitMQ"""
    global connection, channel
    print("[RabbitMQ] Mencoba reconnect...")

    credentials = pika.PlainCredentials("guest", "guest")
    parameters = pika.ConnectionParameters(
        host="31.97.106.30",
        port=5679,
        credentials=credentials,
        heartbeat=600,  # cegah idle disconnect
        blocked_connection_timeout=300,
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue="whatsapp_hook_queue", durable=True)
    channel.queue_declare(queue="whatsapp_message_queue", durable=True)
    print("[RabbitMQ] Reconnect berhasil.")


def forward_struk(payload: dict):
    # Ambil channel aktif
    ch = get_channel()

    # Ambil list grup dari API
    group_ids = (
        requests.get("http://31.97.106.30:3000/api/groups/active")
        .json()
        .get("data", None)
    )
    # print(f"Group ids : {json.dumps(group_ids,indent=2)}")

    # Buat estimasi tiba
    max_luncur_str = estimasi_tiba(
        payload.get("distance", 0),
        payload.get("jenis_pengiriman", 0),
        datetime.now(),
    )

    max_luncur_dt = datetime.combine(
        datetime.today(), datetime.strptime(max_luncur_str, "%H:%M").time()
    )
    max_luncur_dt += timedelta(minutes=int(float(payload.get("tambahan_waktu", 0))))
    max_luncur = max_luncur_dt.strftime("%H:%M")

    max_luncur_line = (
        f"MAKSIMAL DILUNCURKAN DARI GUDANG: {max_luncur}"
        if payload.get("jenis_pengiriman") == "FD"
        else f"ESTIMASI SAMPAI: {max_luncur}"
    )

    distance = payload.get("distance", 0)
    if distance > 14:
        distance_str = str(int(distance))
    else:
        distance_str = f"{distance:.1f}"

    result = (
        f"Jarak: {distance_str} km "
        f"(*{payload.get('kelurahan', 'Unk. Kelurahan')}, "
        f"{payload.get('kecamatan', '').replace('Kecamatan ', '').replace('Kec. ', '').replace('kecamatan', '').replace('kec.', '')}*)"
    )

    invoice_lines = [
        f"*ORDERAN WEB BABE* (JANGAN DI PROSES, INI UJI COBA)",
        f"Nama: {payload.get('cust_name', 'Unknown')}",
        f"Nomor Telepon: {payload.get('phone_number', 'Tidak diketahui')}",
        f"Alamat: {payload.get('address', 'Tidak diketahui')}",
        "",
        "",
        max_luncur_line.strip(),
        result,
        "",
        "",
        "Makasih yaa Cah udah Jajan di Babe!",
        f"Total Jajan: {format_idr(payload.get('total_amount',0))} (*{payload.get('payment_type', '').upper()}*)",
        f"Cek Jajanmu di sini: {payload.get('struk_url', '')}\n"
        f"Jam Order: *{datetime.now().strftime('%H:%M')}*",
        "",
        "",
        f"Jenis Pengiriman: {payload.get('jenis_pengiriman', '')}",
        f"*NOTES: {payload.get('notes') or 'Tidak ada catatan tambahan.'}*",
    ]
    print(f"Invoice lines: {json.dumps(invoice_lines, indent=2)}")

    invoice = "\n".join([line for line in invoice_lines if line is not None])

    print("Mulai mengirim invoice ke grup WhatsApp...")
    try:
        for group_id in group_ids:
            group_payload = {
                "command": "send_message",
                "number": payload.get("from_number"),
                "number_recipient": group_id.get("groupId"),
                "message": invoice,
            }
            ch.basic_publish(
                exchange="",
                routing_key="whatsapp_message_queue",
                body=json.dumps(group_payload),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            time.sleep(3)

        # Update log di DB
        with get_db_session() as session:
            log_entry = (
                session.query(StrukLog)
                .filter(StrukLog.order_id == payload.get("order_id"))
                .first()
            )
            if log_entry:
                log_entry.is_forward = True
                session.commit()
            print("Log forwarding berhasil diupdate...")

        print("Selesai mengirim invoice ke grup WhatsApp.")
        return {
            "status": 200,
            "message": "Invoice forwarded successfully",
            "content": invoice,
        }

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return {"status": 500, "message": f"Ada error: {str(e)}", "content": invoice}


def format_idr(amount):
    try:
        amount = int(float(amount))
        return f"IDR {amount:,}".replace(",", ".")
    except Exception:
        return f"IDR {amount}"
