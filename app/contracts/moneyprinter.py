"""Only stock footage preparation is exposed, never MPT paid generation/publishing."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Term = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]


class FootageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    provider: Literal["pexels", "pixabay", "coverr"] = "pexels"
    terms: list[Term] = Field(min_length=1, max_length=3)
    seconds: int = Field(default=15, ge=5, le=30)
    ratio: Literal["9:16", "16:9"] = "9:16"
    expected_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    rights_note: str = Field(min_length=1, max_length=1000)
