import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BAUS_API_KEY","")
TOKEN_ENDPOINT = os.getenv("TOKEN_ENDPOINT","")
def get_access_token() : 
  try : 
    headers = {
      "x-api-key" : API_KEY,
    }

    response = requests.get(headers=headers,url=TOKEN_ENDPOINT)
    response.raise_for_status()
    data = response.json()
    token = data.get("token","")
    return { 
      "success" : True,
      "data" : token
    }
  except Exception as e :
    print(msg:=f"Something went wrong : {e}")
    return { 
      "success" : False,
      "message" : msg 
    }

if __name__ == '__main__' : 
  import json
  token = get_access_token()
  print("Data yang terambil : ")
  print(json.dumps(token,indent=2))