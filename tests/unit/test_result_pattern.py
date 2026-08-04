"""
Unit tests for the Result pattern (Ok/Err).
"""
import pytest

from app.domain.common.result import Err, Ok


class TestOk:
    def test_is_ok(self):
        result = Ok(42)
        assert result.is_ok() is True
        assert result.is_err() is False

    def test_unwrap(self):
        result = Ok("hello")
        assert result.unwrap() == "hello"

    def test_unwrap_err_raises(self):
        result = Ok(42)
        with pytest.raises(ValueError):
            result.unwrap_err()

    def test_map(self):
        result = Ok(5)
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_ok()
        assert mapped.unwrap() == 10

    def test_map_err_passthrough(self):
        result = Ok(5)
        mapped = result.map_err(lambda e: "error")
        assert mapped.is_ok()
        assert mapped.unwrap() == 5

    def test_repr(self):
        result = Ok(42)
        assert "Ok" in repr(result)


class TestErr:
    def test_is_err(self):
        result = Err("error")
        assert result.is_err() is True
        assert result.is_ok() is False

    def test_unwrap_err(self):
        result = Err("something went wrong")
        assert result.unwrap_err() == "something went wrong"

    def test_unwrap_raises(self):
        result = Err("error")
        with pytest.raises(ValueError):
            result.unwrap()

    def test_map_passthrough(self):
        result = Err("error")
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_err()
        assert mapped.unwrap_err() == "error"

    def test_map_err(self):
        result = Err("original")
        mapped = result.map_err(lambda e: f"wrapped: {e}")
        assert mapped.is_err()
        assert mapped.unwrap_err() == "wrapped: original"

    def test_repr(self):
        result = Err("error")
        assert "Err" in repr(result)
