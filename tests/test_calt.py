from calt import hello


def test_hello_returns_expected_message() -> None:
    assert hello() == "Hello from calt!"
