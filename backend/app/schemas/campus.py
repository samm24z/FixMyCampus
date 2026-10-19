"""Campus place schema."""

from pydantic import BaseModel, ConfigDict


class PlaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    kind: str
    description: str
