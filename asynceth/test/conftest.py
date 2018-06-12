import pytest
import testing.parity
import signal
from aiohttp import web

@pytest.fixture
def parity(loop):
    parity = testing.parity.ParityServer()
    yield parity
    parity.stop(_signal=signal.SIGKILL)
