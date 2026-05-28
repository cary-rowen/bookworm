from types import SimpleNamespace

import pytest

from bookworm import speech


class FakePrismError(Exception):
    pass


class FakeBackend:
    def __init__(self, features=None):
        self.features = features or SimpleNamespace(
            supports_output=True,
            supports_speak=True,
            supports_braille=True,
        )
        self.calls = []

    def output(self, text, interrupt=False):
        self.calls.append(("output", text, interrupt))

    def speak(self, text, interrupt=False):
        self.calls.append(("speak", text, interrupt))

    def braille(self, text):
        self.calls.append(("braille", text))


class ContextFactory:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self

    def create_best(self):
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


@pytest.fixture(autouse=True)
def reset_speech(monkeypatch):
    speech._reset_output()
    monkeypatch.setattr(
        speech.config,
        "conf",
        {"general": {"announce_ui_messages": True}},
    )
    yield
    speech._reset_output()


def install_fake_prism(monkeypatch, result):
    factory = ContextFactory(result)
    monkeypatch.setattr(
        speech._output_cache,
        "prism",
        SimpleNamespace(Context=factory, PrismError=FakePrismError),
    )
    return factory


@pytest.mark.parametrize(
    ("message", "enabled"),
    [
        ("", True),
        ("hello", False),
    ],
)
def test_announce_does_not_initialize_output_when_unnecessary(
    monkeypatch,
    message,
    enabled,
):
    backend = FakeBackend()
    factory = install_fake_prism(monkeypatch, backend)
    speech.config.conf["general"]["announce_ui_messages"] = enabled

    speech.announce(message)

    assert factory.calls == 0
    assert backend.calls == []


def test_announce_uses_prism_output_and_reuses_backend(monkeypatch):
    backend = FakeBackend()
    factory = install_fake_prism(monkeypatch, backend)

    speech.announce("first", urgent=True)
    speech.announce("second")

    assert factory.calls == 1
    assert backend.calls == [
        ("output", "first", True),
        ("output", "second", False),
    ]


def test_announce_falls_back_to_supported_speech_and_braille(monkeypatch):
    backend = FakeBackend(
        features=SimpleNamespace(
            supports_output=False,
            supports_speak=True,
            supports_braille=True,
        ),
    )
    install_fake_prism(monkeypatch, backend)

    speech.announce("hello", urgent=True)

    assert backend.calls == [
        ("speak", "hello", True),
        ("braille", "hello"),
    ]


def test_announce_silently_ignores_missing_prism_backend(monkeypatch):
    factory = install_fake_prism(monkeypatch, ValueError("no backend"))

    speech.announce("hello")

    assert factory.calls == 1


def test_announce_silently_ignores_prism_import_failure(monkeypatch):
    calls = []

    def raise_import_error(name):
        calls.append(name)
        raise OSError

    monkeypatch.setattr(speech, "import_module", raise_import_error)

    speech.announce("hello")

    assert calls == ["prism"]
