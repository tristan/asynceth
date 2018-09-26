import os
import json
import subprocess
from ethereum.utils import decode_hex

def compile_solidity(sourcecode, name=None, cwd=None, optimize=True, optimize_runs=1000000000):

    args = ['solc', '--allow-paths', '.', '--combined-json', 'bin,abi']
    if optimize:
        args.append('--optimize')
    if optimize_runs:
        args.extend(['--optimize-runs', str(optimize_runs)])

    if cwd is None:
        cwd = "."
    cwd = os.path.abspath(cwd)

    if os.path.exists(os.path.join(cwd, sourcecode)):
        filename = sourcecode
        sourcecode = None
    else:
        filename = '<stdin>'

    args.append(filename)

    process = subprocess.Popen(args, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, stderrdata = process.communicate(input=sourcecode)
    try:
        output = json.loads(output)
    except json.JSONDecodeError:
        if output and stderrdata:
            output += b'\n' + stderrdata
        elif stderrdata:
            output = stderrdata
        raise Exception("Failed to compile source: {}\n{}\n{}".format(filename, ' '.join(args), output.decode('utf-8')))

    contract = None
    try:
        for key in output['contracts']:
            if key.startswith(filename + ':'):
                if name is not None and not key.endswith(':' + name):
                    continue
                contract = output['contracts'][key]
                break
    except KeyError:
        raise
    if contract is None:
        raise Exception("Unexpected compiler output: unable to find contract in result")

    abi = json.loads(contract['abi'])
    data = decode_hex(contract['bin'])

    return abi, data
