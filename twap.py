#!/usr/bin/env python3

import time
import datetime
import argparse
from web3 import Web3
from dotenv import load_dotenv
import requests
import os

load_dotenv()

# etherscan.io API:
etherscan_api = "https://api.etherscan.io/api"

# Get API keys from .env file:
etherscan_key = os.environ.get("ETHERSCAN_KEY")
alchemy_key = os.environ.get("ALCHEMY_KEY")

# default TWAP period in minutes:
DEFAULT_PERIOD = 2

# Some tokens don't have ABI available, hence, use WETH for all ERC-20 tokens:
weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

def load_abi(abi_address):
  API_ENDPOINT = etherscan_api+"?module=contract&action=getabi&address="+str(abi_address)+"&apikey="+etherscan_key
  r = requests.get(url = API_ENDPOINT)
  response = r.json()
  return response["result"]

def load_token(token_address):
  ABI = load_abi(weth_address)
  return w3.eth.contract(address=token_address, abi=ABI)

def load_contract(contract_address):
  ABI = load_abi(contract_address)
  return w3.eth.contract(address=contract_address, abi=ABI)

def get_block(timestamp):
  API_ENDPOINT = etherscan_api+"?module=block&action=getblocknobytime&closest=before&timestamp="+str(timestamp)+"&apikey="+etherscan_key
  r = requests.get(url = API_ENDPOINT)
  response = r.json()
  return int(response["result"])

parser = argparse.ArgumentParser()
parser.add_argument("contract", type=str, help="calculate TWAP for this pool address")
parser.add_argument("-t", "--timestamp", type=str, help="calculate TWAP ending at this timestamp")
parser.add_argument("-p", "--period", type=int, help="TWAP period in minutes")
parser.add_argument("-b", "--block", type=int, help="calculate TWAP ending at this block")
parser.add_argument("-f", "--first_block", type=int, help="calculate TWAP starting at this block")
args = parser.parse_args()

# HTTPProvider:
w3 = Web3(Web3.HTTPProvider('https://eth-mainnet.alchemyapi.io/v2/'+alchemy_key))

pool_address = args.contract

if args.timestamp:
  timestamp = int(args.timestamp)
else:
  timestamp = int(time.time())

if args.period:
  period = args.period
else:
  period = DEFAULT_PERIOD

if args.block:
  block_2 = args.block
  timestamp = w3.eth.getBlock(block_2).timestamp
  if args.first_block:
    block_1 = args.first_block
    period = (timestamp - w3.eth.getBlock(block_1).timestamp) / 60
  else:
    block_1 = get_block(str(int(w3.eth.getBlock(block_2).timestamp-period*60))) 
elif args.timestamp:
  block_2 = get_block(timestamp)
  block_1 = get_block(str(timestamp-period*60))
else:
  block_2 = w3.eth.blockNumber
  block_1 = get_block(str(timestamp-period*60))

print('Calculating TWAP ending at %s UTC for %.2fm period' % (datetime.datetime.utcfromtimestamp(timestamp), period))

timestamp_1 = w3.eth.getBlock(block_1).timestamp
timestamp_2 = w3.eth.getBlock(block_2).timestamp

pool_contract = load_contract(w3.toChecksumAddress(pool_address))

price_0_cumulative_1 = pool_contract.functions.price0CumulativeLast().call(block_identifier=block_1)
price_0_cumulative_2 = pool_contract.functions.price0CumulativeLast().call(block_identifier=block_2)
price_1_cumulative_1 = pool_contract.functions.price1CumulativeLast().call(block_identifier=block_1)
price_1_cumulative_2 = pool_contract.functions.price1CumulativeLast().call(block_identifier=block_2)

reserves_1 = pool_contract.functions.getReserves().call(block_identifier=block_1)
reserves_2 = pool_contract.functions.getReserves().call(block_identifier=block_2)

token0_address = pool_contract.functions.token0().call()
token1_address = pool_contract.functions.token1().call()
token0_contract = load_token(token0_address)
token1_contract = load_token(token1_address)

token0_decimals = token0_contract.functions.decimals().call()
token1_decimals = token1_contract.functions.decimals().call()

twap_0 = (price_0_cumulative_2 + int((reserves_2[1] / reserves_2[0] * (timestamp_2 - reserves_2[2])) * 2 ** 112) - (price_0_cumulative_1 + int((reserves_1[1] / reserves_2[0] * (timestamp_1 - reserves_1[2])) * 2 ** 112))) / (timestamp_2 - timestamp_1) / 2 ** 112 / 10 ** (token1_decimals - token0_decimals)
twap_1 = (price_1_cumulative_2 + int((reserves_2[0] / reserves_2[1] * (timestamp_2 - reserves_2[2])) * 2 ** 112) - (price_1_cumulative_1 + int((reserves_1[0] / reserves_2[1] * (timestamp_1 - reserves_1[2])) * 2 ** 112))) / (timestamp_2 - timestamp_1) / 2 ** 112 / 10 ** (token0_decimals - token1_decimals)

token0_symbol = token0_contract.functions.symbol().call()
token1_symbol = token1_contract.functions.symbol().call()

print('Token 1: %s at %s, %d digits' % (token0_symbol, token0_address, token0_decimals))
print('Token 2: %s at %s, %d digits' % (token1_symbol, token1_address, token1_decimals))
print('%s/%s:' % (token0_symbol, token1_symbol))
print('Block %d at %s UTC: %f' % (block_1, datetime.datetime.utcfromtimestamp(timestamp_1), reserves_1[1] / reserves_1[0] / 10 ** (token1_decimals - token0_decimals)))
print('Block %d at %s UTC: %f' % (block_2, datetime.datetime.utcfromtimestamp(timestamp_2), reserves_2[1] / reserves_2[0] / 10 ** (token1_decimals - token0_decimals)))
print('TWAP: %f' % (twap_0))
print('%s/%s:' % (token1_symbol, token0_symbol))
print('Block %d at %s UTC: %f' % (block_1, datetime.datetime.utcfromtimestamp(timestamp_1), reserves_1[0] / reserves_1[1] / 10 ** (token0_decimals - token1_decimals)))
print('Block %d at %s UTC: %f' % (block_2, datetime.datetime.utcfromtimestamp(timestamp_2), reserves_2[0] / reserves_2[1] / 10 ** (token0_decimals - token1_decimals)))
print('TWAP: %f' % (twap_1))
