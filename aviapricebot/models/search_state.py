from pydantic import BaseModel, Field
from typing import List


class SearchState(BaseModel):
    from_city: str
    where_city: str

    selected_dates: List[str] = Field(default_factory=list)
