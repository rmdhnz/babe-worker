from fastapi import FastAPI
from pydantic import BaseModel
from queue_publisher import publish_order

app = FastAPI()

class Order(BaseModel):
    order_id: int
    order_no: str
    user_id: int
    cells: list
    payment_type: str
    delivery_type_id: int

@app.post("/create_struk_queue")
def create_struk_queue(payload: Order):
    publish_order(payload.dict())
    return {"success": True, "message": "Order accepted and queued"}
