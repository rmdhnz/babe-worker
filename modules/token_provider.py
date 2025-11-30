from modules.sqlalchemy_setup import get_db_session
from modules.models_sqlalchemy import Token


def get_all_tokens() : 
  with get_db_session() as db : 
    token =  db.query(Token).filter(Token.outlet_id==1).first()
    return {
      "outlet_id" : token.outlet_id,
      "token" : token.token
    }