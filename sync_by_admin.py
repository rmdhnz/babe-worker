from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Literal, Optional
from worker_db import SyncProductAndCombo

app = FastAPI()


class SyncRequest(BaseModel):
    user_id: int
    name: str
    outlet_id: int


agent = SyncProductAndCombo()


@app.post("/sync_data")
def sync_data(req: SyncRequest):
    data = req.dict()
    response = agent.sync_now(data)
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("sync_by_admin:app", host="0.0.0.0", port=6968, reload=False)
