import json
import pika
import time
import requests
from datetime import datetime, timedelta
from modules.maps_utility import estimasi_tiba
from modules.models_sqlalchemy import StrukLog
from modules.sqlalchemy_setup import get_db_session

# Konfigurasi koneksi awal
RABBITMQ_HOST = '31.97.106.30'
RABBITMQ_PORT = 5679
RABBITMQ_USER = 'guest'
RABBITMQ_PASS = 'guest'

credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
parameters = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=RABBITMQ_PORT,
    credentials=credentials,
    heartbeat=600,                  # biar koneksi ga idle
    blocked_connection_timeout=300, # batas block
)

connection = None
channel = None

def _connect_rabbit():
    """Buat koneksi baru ke RabbitMQ"""
    global connection, channel
    try:
        print("[RabbitMQ] Mencoba koneksi ke broker...")
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue='whatsapp_hook_queue', durable=True)
        channel.queue_declare(queue='whatsapp_message_queue', durable=True)
        print("[RabbitMQ] Koneksi berhasil.")
    except Exception as e:
        print(f"[RabbitMQ][ERROR] Gagal konek ke RabbitMQ: {e}")
        connection = None
        channel = None

def _get_channel():
    """Pastikan channel aktif, reconnect jika mati"""
    global connection, channel
    try:
        if connection is None or connection.is_closed:
            print("[RabbitMQ] Koneksi hilang, mencoba reconnect...")
            _connect_rabbit()
        if channel is None or channel.is_closed:
            print("[RabbitMQ] Channel hilang, mencoba buat ulang channel...")
            channel = connection.channel()
            channel.queue_declare(queue='whatsapp_hook_queue', durable=True)
            channel.queue_declare(queue='whatsapp_message_queue', durable=True)
        return channel
    except Exception as e:
        print(f"[RabbitMQ][ERROR] Tidak bisa buat channel: {e}")
        _connect_rabbit()
        return channel


# ===== Fungsi utama =====
def forward_struk(payload: dict):
    """Mengirim struk ke semua grup aktif via RabbitMQ"""
    try:
        print("[FORWARD] Mengambil data grup aktif...")
        response = requests.get("http://31.97.106.30:3000/api/groups/active", timeout=10)
        group_ids = response.json().get("data", [])
        print(f"[FORWARD] Total grup ditemukan: {len(group_ids)}")
    except Exception as e:
        print(f"[ERROR] Gagal ambil daftar grup: {e}")
        return {"status": 500, "message": f"Gagal ambil daftar grup: {e}", "content": None}

    # Buat estimasi tiba
    try:
        max_luncur_str = estimasi_tiba(
            payload.get("distance", 0),
            payload.get("jenis_pengiriman", 0),
            datetime.now(),
        )

        max_luncur_dt = datetime.combine(datetime.today(), datetime.strptime(max_luncur_str, "%H:%M").time())
        max_luncur_dt += timedelta(minutes=int(float(payload.get("tambahan_waktu", 0))))
        max_luncur = max_luncur_dt.strftime("%H:%M")

        max_luncur_line = (
            f"MAKSIMAL DILUNCURKAN DARI GUDANG: {max_luncur}"
            if payload.get("jenis_pengiriman") == "FD"
            else f"ESTIMASI SAMPAI: {max_luncur}"
        )
    except Exception as e:
        print(f"[ERROR] Gagal hitung estimasi tiba: {e}")
        max_luncur_line = "Estimasi tidak tersedia"

    # Format invoice
    try:
        distance_val = payload.get("distance", 0)
        distance_str = str(int(distance_val)) if distance_val > 14 else f"{float(distance_val):.1f}"
        invoice_lines = [
            "*ORDERAN WEB BABE*\n",
            f"Nama: {payload.get('cust_name', 'Unknown')}",
            f"Nomor Telepon: {format_phone_number(payload.get('phone_number', 'Tidak diketahui'))}\n",
            f"Alamat: {payload.get('address', 'Tidak diketahui')}",
            "",
            max_luncur_line.strip(),
            f"Jarak: {distance_str} km (*{payload.get('kelurahan', 'Unk. Kelurahan')}, {payload.get('kecamatan', '').replace('Kecamatan ', '').replace('Kec. ', '').replace('kecamatan', '').replace('kec.', '')}*)\n\n",
            "",
            "Makasih yaa Cah udah Jajan di Babe!",
            f"Total Jajan: {format_idr(payload.get('total_amount', 0))} (*{payload.get('payment_type', '').upper()}*)",
            f"Cek Jajanmu di sini: {payload.get('struk_url', '')}",
            f"Jam Order: *{datetime.now().strftime('%H:%M')}*\n",
            "",
            f"Jenis Pengiriman: {payload.get('jenis_pengiriman', '')}",
            f"*NOTES: {payload.get('notes') or 'Tidak ada catatan tambahan.'}*",
        ]
        invoice = "\n".join([line for line in invoice_lines if line])
    except Exception as e:
        print(f"[ERROR] Gagal membentuk invoice: {e}")
        invoice = "Gagal membentuk invoice."

    # Kirim ke semua grup
    try:
        ch = _get_channel()
        for group in group_ids:
            try:
                group_payload = {
                    "command": "send_message",
                    "number": payload.get("from_number"),
                    "number_recipient": group.get("groupId"),
                    "message": invoice,
                }
                ch.basic_publish(
                    exchange='',
                    routing_key='whatsapp_message_queue',
                    body=json.dumps(group_payload),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                print(f"[SEND] Berhasil kirim ke grup: {group.get('groupName', group.get('groupId'))}")
                time.sleep(3)
            except Exception as e:
                print(f"[SEND][ERROR] Gagal kirim ke grup {group.get('groupId')}: {e}")
                _connect_rabbit()
                time.sleep(5)

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

        return {"status": 200, "message": "Invoice forwarded successfully", "content": invoice}
    

    except Exception as e:
        print(f"[FORWARD][ERROR] Gagal kirim invoice: {e}")
        _connect_rabbit()
        return {"status": 500, "message": f"Ada error saat mengirim: {e}", "content": invoice}


def format_idr(amount):
    try:
        amount = int(float(amount))
        return f"IDR {amount:,}".replace(",", ".")
    except Exception:
        return f"IDR {amount}"

def format_phone_number(phone: str) -> str:
    # Hapus spasi dan karakter non-digit di awal
    phone = phone.strip().replace(" ", "").replace("-", "")

    # Jika dimulai dengan +62 → ubah jadi 0
    if phone.startswith("+62"):
        phone = "0" + phone[3:]

    # Jika dimulai dengan 62 → ubah jadi 0
    elif phone.startswith("62"):
        phone = "0" + phone[2:]

    # Jika sudah dimulai dengan 0 → biarkan
    elif phone.startswith("0"):
        phone = phone

    # Jika formatnya lain → tidak diubah tapi dikembalikan untuk debugging
    else:
        phone = phone

    return phone
