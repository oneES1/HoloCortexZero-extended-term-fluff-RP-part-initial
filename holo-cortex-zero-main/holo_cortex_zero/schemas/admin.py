from pydantic import BaseModel

from .message import ret_data_class


class AdminLogin(BaseModel):
    username: str
    password: str


@ret_data_class
class AdminLoginRet(BaseModel):
    access_token: str
    token_type: str


class AdminToken(BaseModel):
    access_token: str
    token_type: str
