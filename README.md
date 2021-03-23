# DeFi tracking scripts in Python

## Install dependencies

Install virtual Python environment builder, e.g. on OpenBSD:

```
doas pkg_add git py3-virtualenv
```

Setup virtual environment:

```
cd defi-tracking/
virtualenv venv
. venv/bin/activate
pip install web3 python-dotenv
```

## Configure API keys

Set `ETHERSCAN_KEY` and `ALCHEMY_KEY` variables in `.env` file

## Scripts

[twap.py](./twap.py) calculates TWAP for Uniswap/Sushiswap pools. This requires access to Ethereum archive node (e.g. [Alchemy](https://www.alchemyapi.io/)

