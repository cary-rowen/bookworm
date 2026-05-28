"""Screen reader and braille output."""

from importlib import import_module
from types import SimpleNamespace

from bookworm import config
from bookworm.logger import logger
from bookworm.signals import reading_position_change

log = logger.getChild(__name__)


_output_cache = SimpleNamespace(prism=None, context=None, output=None)


def _get_prism():
    if _output_cache.prism is None:
        _output_cache.prism = import_module("prism")
    return _output_cache.prism


def _get_output():
    if _output_cache.output is None:
        prism = _get_prism()
        _output_cache.context = prism.Context()
        _output_cache.output = _output_cache.context.create_best()
    return _output_cache.output


def _reset_output():
    _output_cache.prism = None
    _output_cache.output = None
    _output_cache.context = None


def _recoverable_output_exceptions():
    # PrismError is only available after the lazy import succeeds.
    exceptions = [ImportError, OSError, ValueError, RuntimeError]
    if _output_cache.prism is not None:
        exceptions.append(_output_cache.prism.PrismError)
    return tuple(exceptions)


def _output_message(output, message, urgent):
    features = output.features
    if features.supports_output:
        output.output(message, interrupt=urgent)
        return
    if features.supports_speak:
        output.speak(message, interrupt=urgent)
    if features.supports_braille:
        output.braille(message)


def announce(message, urgent=False):
    """Speak and braille a message related to UI."""
    if not config.conf["general"]["announce_ui_messages"]:
        return
    if not message:
        return
    try:
        _output_message(_get_output(), message, urgent)
    except _recoverable_output_exceptions():
        _reset_output()
        log.debug("Failed to announce UI message through Prism.", exc_info=True)


@reading_position_change.connect
def announce_new_reading_position(sender, position, **kwargs):
    del sender, position
    if text_to_announce := kwargs.get("text_to_announce"):
        announce(text_to_announce, urgent=True)
