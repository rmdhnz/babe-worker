from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Literal, Optional
from convert_rawcart_to_ord import StrukMaker

app = FastAPI()


class Cell(BaseModel):
    id: int
    prodvar_id: Optional[str] = None
    name: str
    type: Literal["item", "paket"]
    product_type_id: int
    discount: float = 0.0
    harga_satuan: Optional[int] = 0.0
    harga_total: Optional[int] = 0.0
    variant_id: Optional[int] = None
    variant: Optional[str] = None
    qty: int


class OrderRequest(BaseModel):
    user_id: int
    name: str
    jarak: float
    is_free_ongkir: bool
    telepon: str
    cells: List[Cell]
    outlet_id: int


agent = StrukMaker()


@app.post("/create_struk")
def create_order(order: OrderRequest):
    payload_dict = order.dict()
    response = agent.handle_order(payload_dict)
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("processor_struk:app", host="0.0.0.0", port=6969, reload=False)
