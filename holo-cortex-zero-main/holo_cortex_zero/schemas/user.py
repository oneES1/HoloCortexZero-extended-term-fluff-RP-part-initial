from datetime import datetime

from pydantic import BaseModel

class User(BaseModel):
    id: int
    username: str
    perm_level: int
    login_time: datetime
    is_active: bool = True

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    adapter_key: str
    platform_userid: str


class UserUpdate(BaseModel):
    access_key: str
    username: str
    perm_level: int
