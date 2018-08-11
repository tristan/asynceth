## asynceth

An asyncio ethereum jsonrpc library

## Install

`pip install asynceth`

## Usage Example

```
import asyncio
from asynceth import JsonRPCClient
from asynceth import Contract

async def example_jsonrpc_request():
    client = JsonRPCClient("http://localhost:8485")
    balance = await client.eth_getBalance("0x0000000000000000000000000000000000000000")
    print(balance)

asyncio.get_event_loop().run_until_complete(example_jsonrpc_request())

greeter_code = """
contract Greeter is Mortal {
    /* Define variable greeting of the type string */
    string greeting;

    /* This runs when the contract is executed */
    function Greeter(string _greeting) public {
        greeting = _greeting;
    }

    /* Main function */
    function greet() constant returns (string) {
        return greeting;
    }
}
"""

# NOTE: example requires `solc` to be installed, and private_key must be the private key to an
# account on the ethereum node pointed to by JsonRPCClient that has funds to deploy the contract
private_key = os.urandom(32)
async def example_contract_deployment():
    client = JsonRPCClient("http://localhost:8485")
    greeter = await Contract(client, greeter_code).set_signer(private_key).deploy("Hello World")
    greeting = await greeter.greet()
    assert greeting == "Hello World"

asyncio.get_event_loop().run_until_complete(example_contract_deployment())
```

## Running tests

```
python setup.py test
```

OR

```
virtualenv -p python3 env
env/bin/pip install -r requirements.txt -r requirements-testing.txt
env/bin/py.test
```

## History

##### 0.0.1
* Initial release
