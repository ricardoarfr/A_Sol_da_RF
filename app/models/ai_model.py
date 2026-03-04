from pydantic import BaseModel


class AIModel(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    api_key: str
    active: bool = False
