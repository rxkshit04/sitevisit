import pytest

from apps.leads.phone import normalise_phone


@pytest.mark.parametrize(
    "raw", ["98765 43210", "+91 98765-43210", "09876543210", "919876543210", "9876543210"]
)
def test_same_number_many_formats(raw):
    assert normalise_phone(raw) == "9876543210"


@pytest.mark.parametrize("raw", ["", "12345", "5876543210", "abcdefghij", "98765432101234"])
def test_invalid_numbers(raw):
    with pytest.raises(ValueError):
        normalise_phone(raw)