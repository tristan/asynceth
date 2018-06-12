import sys
import re
import os

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

PY_VER = sys.version_info
if PY_VER < (3, 6):
    raise RuntimeError("ethjsonrpc doesn't support Python version prior 3.6")

install_requires = list(x.strip() for x in open('requirements.txt'))
tests_require = [
    'pytest'
]

def read_version():
    regexp = re.compile(r"^__version__\W*=\W*'([\d.abrc]+)'")
    init_py = os.path.join(os.path.dirname(__file__),
                           'ethjsonrpc', '__init__.py')
    with open(init_py) as f:
        for line in f:
            match = regexp.match(line)
            if match is not None:
                return match.group(1)
        else:
            raise RuntimeError('Cannot find version in ethjsonrpc/__init__.py')

setup(
    name='ethjsonrpc',
    version=read_version(),
    description='Asyncio Ethereum JSON-RPC client',
    long_description=open('README.md').read(),
    author='Tristan King',
    author_email='mail@tristan.sh',
    url='https://github.com/tristan/aio-ethjsonrpc',
    packages=['ethjsonrpc'],
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: Public Domain',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    install_requires=install_requires,
    include_package_data=True,
    tests_require=tests_require
)
