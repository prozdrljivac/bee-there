import pytest
from pydantic import ValidationError

from modules.sources import SourceDraft, SourceUpdate


def test_source_draft_normalizes_input_and_defaults_to_enabled() -> None:
    draft = SourceDraft(
        name="  Cultural Station  ",
        base_url="HTTPS://Example.COM/events",
    )

    assert draft.name == "Cultural Station"
    assert draft.base_url == "https://example.com/events"
    assert draft.enabled is True


def test_source_update_accepts_and_normalizes_partial_changes() -> None:
    update = SourceUpdate(name="  Updated Source  ")

    assert update.name == "Updated Source"
    assert update.base_url is None
    assert update.enabled is None


def test_source_update_rejects_an_empty_change() -> None:
    with pytest.raises(
        ValidationError, match="at least one change is required"
    ):
        SourceUpdate()


@pytest.mark.parametrize("field", ("name", "base_url", "enabled"))
def test_source_update_rejects_null_changes(field: str) -> None:
    with pytest.raises(ValidationError, match="changes cannot be null"):
        SourceUpdate.model_validate({field: None})


def test_source_draft_rejects_blank_names() -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        SourceDraft(name="   ", base_url="https://example.com")


def test_source_draft_rejects_invalid_base_urls() -> None:
    with pytest.raises(ValidationError, match="valid URL"):
        SourceDraft(name="Cultural Station", base_url="not-a-url")
