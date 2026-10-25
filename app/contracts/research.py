"""Keyword research requests and reusable topic-specific source preferences."""

import ipaddress
from datetime import date
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    keyword: str = Field(min_length=1, max_length=500)
    topic_path: list[str] = Field(default_factory=list, max_length=6)
    target_date: date
    preferred_url: HttpUrl | None = None
    search_web: bool = True
    max_sources: int = Field(default=5, ge=1, le=10)

    @field_validator("preferred_url")
    @classmethod
    def public_url(cls, value):
        if value:
            parsed = urlsplit(str(value))
            if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
                raise ValueError("Cần URL web công khai không chứa thông tin đăng nhập.")
            host = parsed.hostname.lower()
            if host == "localhost" or host.endswith(".localhost"):
                raise ValueError("Không dùng địa chỉ nội bộ.")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Không dùng địa chỉ nội bộ.")
        return value

    @field_validator("topic_path")
    @classmethod
    def valid_path(cls, value):
        if any(not part.strip() or len(part) > 80 for part in value):
            raise ValueError("Mỗi cấp chủ đề cần tên từ 1 đến 80 ký tự.")
        return [part.strip() for part in value]


class TopicProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    branch: str = Field(pattern=r"^(research|novel|comic)$")
    topic_path: list[str] = Field(min_length=1, max_length=6)
    preferred_url: HttpUrl | None = None

    _path = field_validator("topic_path")(ResearchRequest.valid_path.__func__)
    _url = field_validator("preferred_url")(ResearchRequest.public_url.__func__)


class ResearchPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profiles: list[TopicProfile] = Field(default_factory=list, max_length=100)

    @field_validator("profiles")
    @classmethod
    def unique_profiles(cls, value):
        keys = [(p.branch, tuple(p.topic_path)) for p in value]
        if len(set(keys)) != len(keys):
            raise ValueError("Không lưu trùng đường dẫn chủ đề.")
        return value
