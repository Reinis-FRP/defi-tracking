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

[twap.py](./twap.py) calculates TWAP for Uniswap/Sushiswap pools. This requires access to Ethereum archive node (e.g. [Alchemy](https://www.alchemyapi.io/))

[compound_repay.py](./compound_repay.py) calculates expected Compound borrow balance in future. Useful when planning to repay only interest amount and keep principal balance fixed.

[exit_pool.py](./exit_pool.py) estimates exit results from UMA LM pools on Balancer. User can provide expected price-id at expiration, synth price in the pool at exit, and relative size of pool at exit. If [config_exit_pool.json](./config_exit_pool.json) is provided, expected settlement price is assumed the same as current price from Coingecko (if available for specific price-id). The script outputs expected results for user either

* closing position before expiration and rebalancing excess/deficit synth tokens from the pool or
* waiting for expiration, withdrawing both pairs from the pool and calling `settleExpired` on the EMP contract

[track_uma.py](./track_uma.py) fetches all deployed contracts and their parameters from UMA protocol on-chain data. Use -t option to fetch historical collateral and synths balances.

TODO:

* optimize fetching all parameters from create transaction
* format output as CSV
