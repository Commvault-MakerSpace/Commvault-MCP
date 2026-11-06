import json
import logging
import stat
import sys

import pytest
from src.cv_mcp.api.tokens import (
    FileTokenStore,
    MemoryTokenStore,
    TokenError,
    build_token_store,
)


class TestMemoryTokenStore:
    def test_get_returns_pair(self):
        store = MemoryTokenStore("acc", "ref")
        assert store.get() == ("acc", "ref")

    def test_set_replaces_pair(self):
        store = MemoryTokenStore("old_acc", "old_ref")
        store.set("new_acc", "new_ref")
        assert store.get() == ("new_acc", "new_ref")

    def test_warning_logged_on_first_set_only(self, caplog):
        caplog.set_level(logging.WARNING, logger="cv_mcp.tokens")
        store = MemoryTokenStore("acc", "ref")
        # First set should trigger warning
        store.set("a1", "r1")
        assert (
            len([r for r in caplog.records if "not persisted" in r.message or "memory only" in r.message])
            == 1
        )

        # Second set should NOT trigger another warning
        store.set("a2", "r2")
        records_after_second = [
            r for r in caplog.records if "not persisted" in r.message or "memory only" in r.message
        ]
        assert len(records_after_second) == 1


class TestFileTokenStore:
    def test_seeded_on_construction_when_missing(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        FileTokenStore(token_file, seed=("acc", "ref"))

        assert token_file.exists()
        if sys.platform != "win32":
            # chmod only toggles the read-only bit on Windows; ACLs guard the file there.
            mode = stat.S_IMODE(token_file.stat().st_mode)
            assert mode == 0o600

        data = json.loads(token_file.read_text())
        assert "access_token" in data
        assert "refresh_token" in data
        assert "rotated_at" in data

    def test_raises_when_missing_and_no_seed(self, tmp_path):
        token_file = tmp_path / "missing.json"
        with pytest.raises(TokenError, match="does not exist"):
            FileTokenStore(token_file)

    def test_get_rereads_file(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        store = FileTokenStore(token_file, seed=("old_acc", "old_ref"))

        # Write new JSON manually
        new_data = {
            "access_token": "new_acc",
            "refresh_token": "new_ref",
            "rotated_at": "2023-01-01T00:00:00+00:00",
        }
        token_file.write_text(json.dumps(new_data))

        assert store.get() == ("new_acc", "new_ref")

    def test_get_raises_on_invalid_json(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text("not json")
        store = FileTokenStore(
            token_file, seed=("acc", "ref")
        )  # Seed creates file, but we overwrite content logic isn't quite right for this test case structure

        # Actually, let's just create the file with bad JSON directly to test get()
        token_file.write_text("bad json")
        store = FileTokenStore.__new__(FileTokenStore)
        store._path = token_file

        with pytest.raises(TokenError):
            store.get()

    def test_get_raises_on_missing_keys(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        token_file.write_text(json.dumps({"access_token": "acc"}))  # Missing refresh_token

        store = FileTokenStore.__new__(FileTokenStore)
        store._path = token_file

        with pytest.raises(TokenError):
            store.get()

    def test_set_creates_parents_and_no_tmp_files(self, tmp_path):
        token_file = tmp_path / "subdir" / "tokens.json"
        store = FileTokenStore.__new__(FileTokenStore)
        store._path = token_file

        store.set("acc", "ref")

        assert token_file.exists()
        # Check for .tmp files in the directory
        tmp_files = list(tmp_path.glob("**/*.tmp"))
        assert len(tmp_files) == 0


class TestBuildTokenStore:
    def test_token_file_with_tokens(self, tmp_path):
        token_file = tmp_path / "tokens.json"
        store = build_token_store(
            access_token="acc",
            refresh_token="ref",
            token_file=str(token_file),
        )
        assert isinstance(store, FileTokenStore)

    def test_token_file_missing_no_tokens(self, tmp_path):
        token_file = tmp_path / "missing.json"
        with pytest.raises(TokenError):
            build_token_store(
                access_token=None,
                refresh_token=None,
                token_file=str(token_file),
            )

    def test_no_token_file_with_tokens(self):
        store = build_token_store(
            access_token="acc",
            refresh_token="ref",
            token_file=None,
        )
        assert isinstance(store, MemoryTokenStore)

    def test_nothing_raises(self):
        with pytest.raises(TokenError):
            build_token_store(
                access_token=None,
                refresh_token=None,
                token_file=None,
            )
