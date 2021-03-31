#!/usr/bin/env python3

import argparse
import json
from web3 import Web3
from dotenv import load_dotenv
import requests
import os
import sys

load_dotenv()

# etherscan.io API:
etherscan_api = "https://api.etherscan.io/api"

# Coingecko API:
coingecko_api = "https://api.coingecko.com/api/v3"

# Get API keys from .env file:
etherscan_key = os.environ.get("ETHERSCAN_KEY")
alchemy_key = os.environ.get("ALCHEMY_KEY")

# Some tokens don't have ABI available, hence, use WETH for all ERC-20 tokens:
weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

# Config json file
config_file = 'config_exit_pool.json'

# EMP contract registration event signature:
EMP_REGISTER = 'CreatedExpiringMultiParty(address,address)'

# Default scaling:
DECIMALS = 18

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

def first_internal(contract_address):
  API_ENDPOINT = etherscan_api+"?module=account&action=txlistinternal&address="+contract_address+"&sort=asc&apikey="+etherscan_key
  r = requests.get(url = API_ENDPOINT)
  response = r.json()
  if response["status"] == '0':
    return None
  if response["result"][0]["type"] == "create" and response["result"][0]["isError"] == '0':
    return response["result"][0]
  else:
    return None

def get_emp(tx):
  tx_logs = w3.eth.getTransactionReceipt(tx["hash"]).logs
  if tx_logs == []:
    return None
  for event in tx_logs:
    if event["topics"][0] == register_event_hash:
      return w3.toChecksumAddress('0x'+event["topics"][1].hex()[26:])
  return None

def load_creation(contract_address):
  creation_tx = first_internal(contract_address)
  if creation_tx:
    return get_emp(creation_tx)
  else:
    return None

def safe_div(x, y):
  if x == 0 and y == 0:
    return 0
  return x / y

def get_coingecko(price_identifier):
  if price_identifier not in config["price_id_coingecko"]:
    return None
  id = config["price_id_coingecko"][price_identifier]["id"]
  vs = config["price_id_coingecko"][price_identifier]["vs_currency"]
  API_ENDPOINT = coingecko_api+"/simple/price?ids="+id+"&vs_currencies="+vs
  r = requests.get(url = API_ENDPOINT)
  response = r.json()
  if id not in response:
    return None
  if vs not in response[id]:
    return None
  if config["price_id_coingecko"][price_identifier]["inverse"]:
    return 1 / response[id][vs]
  else:
    return response[id][vs]

parser = argparse.ArgumentParser()
parser.add_argument("pool", type=str, help="calculate exit from this Balancer pool")
parser.add_argument("address", type=str, help="user address")
parser.add_argument("-s", "--settlement_price", type=str, help="Expected settlement price on expiration")
parser.add_argument("-r", "--relative", type=str, help="relative pool size at exit (1=100%) without user position")
parser.add_argument("-p", "--pool_price", type=str, help="synth price in pool at exit")
args = parser.parse_args()

try:
  with open(config_file, 'r') as f:
    config = json.load(f)
except FileNotFoundError:
  config = {"price_id_coingecko": {}}

if args.relative:
  relative = float(args.relative)
else:
  relative = 1

if args.settlement_price:
  settlement_price = float(args.settlement_price)
else:
  settlement_price = None

# HTTPProvider:
w3 = Web3(Web3.HTTPProvider('https://eth-mainnet.alchemyapi.io/v2/'+alchemy_key))

pool_address = w3.toChecksumAddress(args.pool)
user_address = w3.toChecksumAddress(args.address)

register_event_hash = w3.keccak(text=EMP_REGISTER)

token_abi = load_abi(weth_address)

pool_contract = load_contract(pool_address)

if pool_contract.functions.getNumTokens().call() != 2:
  sys.exit("This script works only with 2 Balancer pool tokens")

pool_tokens = pool_contract.functions.getFinalTokens().call()

emp_address = load_creation(pool_tokens[0])
if emp_address:
  synth_address = pool_tokens[0]
  pair_address = pool_tokens[1]
else:
  emp_address = load_creation(pool_tokens[1])
  if emp_address:
    synth_address = pool_tokens[1]
    pair_address = pool_tokens[0]
  else:
    sys.exit("Cannot find EMP synth token in the pool")

emp_contract = load_contract(emp_address)
if emp_contract.functions.contractState().call() != 0:
  sys.exit("This script works only with open EMP contracts")

if not settlement_price:
  settlement_price = get_coingecko(emp_contract.functions.priceIdentifier().call().strip(b'\x00').decode())
  if not settlement_price:
    sys.exit("This price identifier does not have Coingecko source. Set expected expiration with '--settlement-price' option")

collateral_address = emp_contract.functions.collateralCurrency().call()
collateral_contract = load_token(collateral_address)
collateral_symbol = collateral_contract.functions.symbol().call()
collateral_decimals = collateral_contract.functions.decimals().call()

pair_contract = load_token(pair_address)
pair_symbol = pair_contract.functions.symbol().call()
pair_decimals = pair_contract.functions.decimals().call()

synth_contract = load_token(synth_address)
synth_symbol = synth_contract.functions.symbol().call()
synth_decimals = synth_contract.functions.decimals().call()
user_synth_balance = synth_contract.functions.balanceOf(user_address).call()

cum_fee_mul = emp_contract.functions.cumulativeFeeMultiplier().call()
user_positions = emp_contract.functions.positions(user_address).call()
if user_positions[1] != 0:
  sys.exit("This script does not handle pending withrawal requests")
user_debt = user_positions[0][0]
user_collateral = int(user_positions[3][0] * cum_fee_mul / 10 ** DECIMALS)

pool_shares = pool_contract.functions.totalSupply().call()
user_shares = pool_contract.functions.balanceOf(user_address).call()
synth_pool_balance = pool_contract.functions.getBalance(synth_address).call()
synth_pool_weight = pool_contract.functions.getNormalizedWeight(synth_address).call()
pair_pool_balance = pool_contract.functions.getBalance(pair_address).call()
pair_pool_weight = pool_contract.functions.getNormalizedWeight(pair_address).call()
pool_v = synth_pool_balance ** (synth_pool_weight / 10 ** DECIMALS) * pair_pool_balance ** (pair_pool_weight / 10 ** DECIMALS)
current_pool_price = safe_div(pair_pool_balance / (pair_pool_weight / 10 ** DECIMALS) / 10 ** pair_decimals, synth_pool_balance / (synth_pool_weight / 10 ** DECIMALS) / 10 ** synth_decimals)
current_synth_pool_balance = synth_pool_balance
current_pair_pool_balance = pair_pool_balance

# Rebalance pool to keep the same value at exit if pool price provided
if args.pool_price:
  pool_price = float(args.pool_price)
  price_scaling = 10 ** (pair_decimals - synth_decimals) 
  pair_pool_balance = (pool_v / ((pool_v / ((pool_price * price_scaling) ** (pair_pool_weight / 10 ** DECIMALS) * (pair_pool_weight / synth_pool_weight) ** (pair_pool_weight / 10 ** DECIMALS))) ** (synth_pool_weight / 10 ** DECIMALS))) ** (1 / (pair_pool_weight / 10 ** DECIMALS)) 
  synth_pool_balance = pool_v / ((pool_price * price_scaling) ** (pair_pool_weight / 10 ** DECIMALS) * (pair_pool_weight / synth_pool_weight) ** (pair_pool_weight / 10 ** DECIMALS))
else:
  pool_price = current_pool_price

user_synth_pool = int(safe_div(synth_pool_balance, pool_shares) * user_shares)
user_pair_pool = int(safe_div(pair_pool_balance, pool_shares) * user_shares)

# Adjust pool size after exit and factor in relative size if provided:
synth_pool_balance = int((synth_pool_balance - user_synth_pool) * relative)
pair_pool_balance = int((pair_pool_balance - user_pair_pool) * relative)

swap_fee = pool_contract.functions.getSwapFee().call()

if user_synth_pool + user_synth_balance > user_debt:
  swap_pair = pool_contract.functions.calcOutGivenIn(synth_pool_balance, synth_pool_weight, pair_pool_balance, pair_pool_weight, user_synth_pool + user_synth_balance - user_debt, swap_fee).call()
elif user_synth_pool + user_synth_balance < user_debt:
  swap_pair = -pool_contract.functions.calcInGivenOut(pair_pool_balance, pair_pool_weight, synth_pool_balance, synth_pool_weight, user_debt - user_synth_pool - user_synth_balance, swap_fee).call()
else:
  swap_pair = 0

user_redeemable = (user_synth_pool + user_synth_balance) / 10 ** synth_decimals * settlement_price + max(0, user_collateral / 10 ** collateral_decimals - user_debt / 10 ** synth_decimals * settlement_price)

print('Pool balances:')
print('  %f %s' % (current_synth_pool_balance / 10 ** synth_decimals, synth_symbol))
print('  %f %s' % (current_pair_pool_balance / 10 ** pair_decimals, pair_symbol))
print('Current synth price from the pool: %f' % (current_pool_price))
print('User now holds %f share in the pool and at exit (price = %f) can withdraw:' % (safe_div(user_shares, pool_shares), pool_price))
print('  %f %s' % (user_synth_pool / 10 ** synth_decimals, synth_symbol))
print('  %f %s' % (user_pair_pool / 10 ** pair_decimals, pair_symbol))
print('User position in EMP contract:')
print('  %f %s debt' % (user_debt / 10 ** synth_decimals, synth_symbol))
print('  %f %s locked collateral' % (user_collateral / 10 ** collateral_decimals, collateral_symbol))
print('User holds: %f %s' % (user_synth_balance / 10 ** synth_decimals, synth_symbol))
if swap_pair > 0:
  print('A: User sells excess synths to pool and redeems %f %s collateral. User gets net %f %s from pair' % (user_collateral / 10 ** collateral_decimals, collateral_symbol, (user_pair_pool + swap_pair) / 10 ** pair_decimals, pair_symbol))
elif swap_pair < 0:
  print('A: User buys missing synths from pool and redeems %f %s collateral. User gets net %f %s from pair' % (user_collateral / 10 ** collateral_decimals, collateral_symbol, (user_pair_pool + swap_pair) / 10 ** pair_decimals, pair_symbol))
else:
  print('A: User redeems %f %s collateral and gets % f %s from pair' % (user_collateral / 10 ** collateral_decimals, collateral_symbol, user_pair_pool / 10 ** pair_decimals, pair_symbol))
print('B: After exit user can settle for %f %s collateral and keeps %f %s from pair' % (user_redeemable, collateral_symbol, user_pair_pool / 10 ** pair_decimals, pair_symbol))

