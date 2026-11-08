"""Typed learning units: one vocabulary sense, pattern, sample or exercise per item."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TopicInput(StrictModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    parent_id: UUID | None = None


class Source(StrictModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    url: HttpUrl | None = None
    rights_note: Text


class Vocabulary(StrictModel):
    lemma: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    part_of_speech: Literal["noun", "verb", "adjective", "adverb", "phrase", "other"]
    sense: Text
    ipa_uk: str = Field(default="", max_length=200)
    definition: Text
    examples: list[Text] = Field(min_length=1, max_length=8)


class Pattern(StrictModel):
    form: Text
    function: Text
    explanation: Text
    examples: list[Text] = Field(min_length=1, max_length=8)


class Annotation(StrictModel):
    quote: Text
    note: Text


class Sample(StrictModel):
    skill: Literal["speaking", "writing"]
    prompt: Text
    response: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)
    ]
    annotations: list[Annotation] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def quotes_exist(self):
        if any(a.quote not in self.response for a in self.annotations):
            raise ValueError("Annotation phải trích đúng đoạn trong sample.")
        return self


class Exercise(StrictModel):
    question: Text
    options: list[Text] = Field(default_factory=list, max_length=8)
    answer: Text
    explanation: Text

    @model_validator(mode="after")
    def answer_in_options(self):
        if self.options and self.answer not in self.options:
            raise ValueError("Đáp án phải thuộc các lựa chọn.")
        if len(set(self.options)) != len(self.options):
            raise ValueError("Lựa chọn không được trùng nhau.")
        return self


class ItemInput(StrictModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    topic_ids: list[UUID] = Field(min_length=1, max_length=10)
    source: Source
    data: Vocabulary | Pattern | Sample | Exercise

    @model_validator(mode="after")
    def distinct_topics(self):
        if len(set(self.topic_ids)) != len(self.topic_ids):
            raise ValueError("Topic không được trùng nhau.")
        return self


class ImportInput(StrictModel):
    kind: Literal["vocabulary", "patterns", "samples", "exercises"]
    items: list[ItemInput] = Field(min_length=1, max_length=100)


class ItemReview(StrictModel):
    expected_version: int = Field(ge=1)
    reviewer: Text
    note: Text


class BriefInput(StrictModel):
    expected_version: int = Field(ge=1)
    focus_text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=650)
    ]


class ItemUpdate(ItemInput):
    expected_version: int = Field(ge=1)
