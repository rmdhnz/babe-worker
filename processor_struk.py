from re import S
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from convert_rawcart_to_ord import StrukMaker
from modules.maps_utility import estimasi_tiba
from datetime import datetime, timedelta

app = FastAPI()


class Cell(BaseModel):
    id: int
    prodvar_id: Optional[str] = None
    name: str
    type: Literal["item", "paket"]
    product_type_id: int
    disc: float = 0.0
    harga_satuan: Optional[int] = 0.0
    harga_total: Optional[int] = 0.0
    variant_id: Optional[int] = None
    variant: Optional[str] = None
    qty: int


class OrderRequest(BaseModel):
    user_id: int
    name: str
    jarak: float
    address: str
    is_free_ongkir: bool
    formatted_address: str
    telepon: str
    cells: List[Cell]
    outlet_id: int
    payment_type: Optional[str] = None
    lunas: Optional[bool] = False
    express_delivery: Optional[bool] = False
    delivery_type_id: Optional[int] = None
    notes: Optional[str] = None


class PayloadRequest(BaseModel):
    cust_name: str = Field(default="Unknown", description="Nama customer")
    phone_number: str = Field(
        default="Tidak diketahui", description="Nomor telepon customer"
    )
    distance: Optional[float] = Field(default=None, description="Jarak order dalam km")
    address: str = Field(
        default="Tidak diketahui", description="Alamat atau URL Google Maps"
    )
    kecamatan: Optional[str] = Field(default=None, description="Nama kecamatan")
    kelurahan: Optional[str] = Field(default=None, description="Nama kelurahan")
    total_amount: float = Field(default=0, description="Total harga jajan")
    payment_type: str = Field(default="unknown", description="Tipe pembayaran")
    jenis_pengiriman: Optional[str] = Field(
        default=None, description="Jenis pengiriman"
    )
    notes: Optional[str] = Field(default=None, description="Catatan tambahan")
    struk_url: Optional[str] = Field(default=None, description="URL struk order")
    status: str = Field(default="unknown", description="Status pembayaran")
    tambahan_waktu: int = Field(
        default=0, description="Tambahan waktu pengiriman dalam menit"
    )
    from_number: Optional[str] = Field(
        default=None, description="Nomor pengirim (outlet)"
    )


class PayloadEstimation(BaseModel):
    distance: float
    jenis_pengiriman: str
    tambahan_waktu: int = 0


agent = StrukMaker()


@app.post("/create_struk")
def create_order(order: OrderRequest):
    payload_dict = order.dict()
    response = agent.handle_order(payload_dict)
    return response


@app.post("/estimation_time")
def estimation_time(payload: PayloadEstimation):
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
    return {
        "estimasi_tiba": max_luncur,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("processor_struk:app", host="0.0.0.0", port=6969, reload=False)
