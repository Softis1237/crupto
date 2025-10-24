from setuptools import setup, find_packages

setup(
    name="crupto",
    version="0.1.0",
    packages=find_packages(include=['prod_core*', 'brain_orchestrator*']),
    install_requires=[
        'ccxt',
        'aiohttp',
        'pyyaml',
        'python-dotenv'
    ],
)