from typing import Literal

from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"