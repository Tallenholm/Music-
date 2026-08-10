from music_app.domain import TrackTags
from music_app.library.tags import SUPPORTED_WRITE_FIELDS, build_changes


def test_build_changes_omits_unchanged_values() -> None:
    current = TrackTags(title="Song", artist="Artist")
    proposed = TrackTags(title="Song", artist="Artist")
    assert build_changes(current, proposed) == ()


def test_build_changes_does_not_erase_nonblank_with_blank() -> None:
    current = TrackTags(title="Song")
    proposed = TrackTags(title="")
    assert build_changes(current, proposed) == ()


def test_build_changes_normalizes_whitespace_for_comparison() -> None:
    current = TrackTags(title="  One   More Time ")
    proposed = TrackTags(title="One More Time")
    assert build_changes(current, proposed) == ()


def test_build_changes_returns_supported_differences() -> None:
    current = TrackTags(title="Old", genre="Rock")
    proposed = TrackTags(title="New", genre="Electronic")
    changes = build_changes(current, proposed)
    assert [(change.field, change.old, change.new) for change in changes] == [
        ("title", "Old", "New"),
        ("genre", "Rock", "Electronic"),
    ]
    assert {change.field for change in changes} <= SUPPORTED_WRITE_FIELDS
