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

##### 0.0.2
* Add basic support for ABIv2

##### 0.0.3
* Use eth-abi==2.0.0-beta.1
* Add TransactionResponse class

##### 0.0.4
* Fix packaging issues

##### 0.0.5
* Allow `null` in `eth_getLogs` topics

##### 0.0.6
* Support network id and use bulk jsonrpc requests in contract calls

##### 0.0.7
* Support supplying name and cwd for contract compilation

##### 0.0.8
* Allow constant contract calls to be called from bulk

##### 0.0.9
* Allow `eth_getLogs` to retry automatically if the requested block number was not found

##### 0.0.10
* Allow specifying the executable to use for solc

##### 0.0.11
* File aiohttp session timout depreciation warning
* Ignore retry logic if the request is cancelled

##### 0.0.12
* Add support for running simple middleware before and after requests

##### 0.0.13
* Include the nonce used in the transaction response
* Add support for solc 0.6 features
* Use solc defaults for `--optimize-runs`
