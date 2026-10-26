"""Public input contracts for the Sources module."""

from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    HttpUrl,
    StringConstraints,
    model_validator,
)


def _validate_base_url(value: str) -> str:
    return str(HttpUrl(value))


RequiredText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
OptionalText = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    | None
)
BaseUrl = Annotated[str, AfterValidator(_validate_base_url)]


class CandidateListing(BaseModel):
    """One event listing retrieved from a configured source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_url: BaseUrl
    content: RequiredText
    external_id: OptionalText = None


class SourceUpdate(BaseModel):
    """Validated changes to an existing source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: RequiredText | None = None
    base_url: BaseUrl | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> Self:
        """Require at least one field to be supplied."""
        if not self.model_fields_set:
            raise ValueError("at least one change is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("changes cannot be null")
        return self


class SourceDraft(BaseModel):
    """Source data accepted when creating a source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: RequiredText
    base_url: BaseUrl
    enabled: bool = True
