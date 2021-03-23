#!/usr/bin/env python3

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

# default time till transaction in minutes:
DEFAULT_TIME = 2

# approx 4 blocks per minute:
BLOCKS_PER_MINUTE = 4

# Mantissa in Compound contracts:
mantissa = 10 ** 18

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

parser = argparse.ArgumentParser()
parser.add_argument("contract", type=str, help="calculate repay amount for this contract")
parser.add_argument("address", type=str, help="user address")
parser.add_argument("-k", "--keep", type=str, help="calculate repay amount targeting this balance")
parser.add_argument("-t", "--time", type=str, help="time in minutes till borrow balance calculation")
args = parser.parse_args()

# HTTPProvider:
w3 = Web3(Web3.HTTPProvider('https://eth-mainnet.alchemyapi.io/v2/'+alchemy_key))

contract_address = args.contract
my_address = args.address 

if args.keep:
  keep_balance = float(args.keep)
else:
  keep_balance = 0

if args.time:
  transaction_time = int(args.time)
else:
  transaction_time = DEFAULT_TIME

transaction_block = w3.eth.blockNumber + transaction_time * BLOCKS_PER_MINUTE

contract = load_contract(w3.toChecksumAddress(contract_address))

decimals = contract.functions.decimals().call()
underlying = contract.functions.underlying().call()

underlying_contract = load_token(underlying)
underlying_decimals = underlying_contract.functions.decimals().call()
underlying_symbol = underlying_contract.functions.symbol().call()

accrual_block_number = contract.functions.accrualBlockNumber().call()
borrow_balance_stored = contract.functions.borrowBalanceStored(my_address).call()
borrow_rate_per_block = contract.functions.borrowRatePerBlock().call()

add_borrow_interest = int(borrow_rate_per_block * (transaction_block - accrual_block_number) * borrow_balance_stored / mantissa)
transaction_borrow_balance = borrow_balance_stored + add_borrow_interest

print('Borrow balance at transaction at block # %d : %f %s' % (transaction_block, transaction_borrow_balance / 10 ** underlying_decimals, underlying_symbol))
print('Repay: %f %s' % (transaction_borrow_balance / 10 ** underlying_decimals - keep_balance, underlying_symbol))
print('Remaining balance: %f %s' % (keep_balance, underlying_symbol))
