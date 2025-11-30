from fastapi import Header, HTTPException
import os
from dotenv import load_dotenv
load_dotenv()

BAUS_API_KEY = os.getenv("BAUS_API_KEY")

def check_api_key(x_api_key: str = Header(None)) : 
  if x_api_key != BAUS_API_KEY : 
    raise HTTPException(
      status_code=401,
      detail="Unauthorized - Invalid API Key"
    )