import pytest
import testing.parity
import signal
from asynceth import Contract, JsonRPCClient

@pytest.fixture
def parity(loop):
    parity = testing.parity.ParityServer()
    yield parity
    parity.stop(_signal=signal.SIGKILL)

@pytest.fixture
def jsonrpc(parity):
    return JsonRPCClient(parity.url())

@pytest.fixture
def abiv2_contract(loop, parity, jsonrpc):
    return loop.run_until_complete(
        Contract(jsonrpc, "asynceth/test/ABIv2Test.sol")
        .set_signer(parity.get_faucet_private_key())
        .deploy())
