#!/usr/bin/env python3

import time
import datetime
import json
import csv
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

# ETH node API:
eth_node_api = os.environ.get("ETH_NODE_API")

# Some tokens don't have ABI available, hence, use WETH for all ERC-20 tokens:
weth_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

# Finder contract address:
finder_address = "0x40f941E48A552bF496B154Af6bf55725f18D77c3"

# EMP contract creation event signature:
EMP_CREATE = 'CreatedExpiringMultiParty(address,address)'

# Perpetual contract creation event signature:
PERP_CREATE = 'CreatedPerpetual(address,address)'

# Jarvis contract creation event signature:
JARVIS_CREATE = 'DerivativeDeployed(uint8,address,address)'

# Jarvis contract creation event signature:
JARVIS_SELF_CREATE = 'SelfMintingDerivativeDeployed(uint8,address)'

# Possible EMP contract states:
EMP_STATES = ('Open', 'ExpiredPriceRequested', 'ExpiredPriceReceived')

# Default scaling:
DECIMALS = 18

# Use the same ABI for all EMP contracts (will fetch it for the first EMP discovered):
emp_abi = []

# Use the same ABI for all Perpetual contracts (will fetch it for the first Perpetual discovered):
perp_abi = []

# Use the same ABI for all Jarvis v1 contracts (will fetch it for the first Jarvis v1 discovered):
jarvis_v1_abi = []

# Use the same ABI for all Jarvis v2 contracts (will fetch it for the first Jarvis v2 discovered):
jarvis_v2_abi = []

# Use the same ABI for all Jarvis Self Minting contracts (will fetch it for the first Jarvis Self Minting discovered):
jarvis_self_abi = []

# Cache json file
cache_file = 'cache.json'

# CSV file name
csv_name = 'contracts.csv'

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

def print_cache(registered_address):
  print('Contract: %s' % (registered_address))
  print('  Contract type: %s' % (cache[registered_address]['type']))
  print('  Deployed at: %s UTC' % (datetime.datetime.utcfromtimestamp(cache[registered_address]['deployed_at'])))
  print('  Deployer: %s' % (cache[registered_address]['deployer']))
  print('  Collateral: %s' % (cache[registered_address]['collateral_symbol']))
  print('  Synth token: %s' % (cache[registered_address]['synth_symbol']))
  print('  Collateral requirement: %f' % (cache[registered_address]['collateral_requirement']))
  if cache[registered_address]['contract_state']:
    print('  Contract state: %s' % (cache[registered_address]['contract_state']))
  if cache[registered_address]['expires_at']:
    print('  Expires at: %s UTC' % (datetime.datetime.utcfromtimestamp(cache[registered_address]['expires_at'])))
  print('  Price identifier: %s' % (cache[registered_address]['price_id']))
  print('  Minimum sponsor tokens %f' % (cache[registered_address]['min_sponsor_tokens']))
  print('  Liquidation liveness: %f hours' % (cache[registered_address]['liquidation_liveness'] / 3600))
  print('  Withdrawal liveness: %f hours' % (cache[registered_address]['withdrawal_liveness'] / 3600))
  print('  Locked collateral: %f %s' % (cache[registered_address]['collateral_locked'], cache[registered_address]['collateral_symbol']))
  print('  Synths minted: %f %s' % (cache[registered_address]['synth_minted'], cache[registered_address]['synth_symbol']))

def get_create(tx):
  tx_logs = w3.eth.getTransactionReceipt(tx["hash"]).logs
  if tx_logs == []:
    return None
  for event in tx_logs:
    if event["topics"][0] == create_emp_event_hash:
      if event["address"].lower() == tx["from"]:
        return {'deployer': w3.toChecksumAddress('0x'+event["topics"][2].hex()[26:]), 'type': 'emp'}
    if event["topics"][0] == create_perp_event_hash:
      if event["address"].lower() == tx["from"]:
        for perp_event in tx_logs:
          if perp_event["topics"][0] == create_jarvis_event_hash and int(perp_event["topics"][1].hex(), 16) == 1: 
            return {'deployer': w3.toChecksumAddress('0x'+event["topics"][2].hex()[26:]), 'type': 'jarvis_v1'}
          elif perp_event["topics"][0] == create_jarvis_event_hash and int(perp_event["topics"][1].hex(), 16) == 2: 
            return {'deployer': w3.toChecksumAddress('0x'+event["topics"][2].hex()[26:]), 'type': 'jarvis_v2'}
          elif perp_event["topics"][0] == create_jarvis_self_event_hash:
            return {'deployer': w3.toChecksumAddress('0x'+event["topics"][2].hex()[26:]), 'type': 'jarvis_self'}
        return {'deployer': w3.toChecksumAddress('0x'+event["topics"][2].hex()[26:]), 'type': 'perp'}
  return None

def load_creation(contract_address):
  creation_tx = first_internal(contract_address)
  if creation_tx:
    create = get_create(creation_tx)
    if create:
      return {'create_time': int(creation_tx["timeStamp"]), 'deployer': create['deployer'], 'type': create['type']}
    else:
      return None
  else:
    return None

def get_block(timestamp):
  API_ENDPOINT = etherscan_api+"?module=block&action=getblocknobytime&closest=before&timestamp="+str(timestamp)+"&apikey="+etherscan_key
  r = requests.get(url = API_ENDPOINT)
  response = r.json()
  return int(response["result"])

def write_csv():
  csv_file = open(csv_name, 'w')
  csv_writer = csv.writer(csv_file, delimiter='\t')
  first_contract = list(cache.keys())[0]
  header = ["registered_address"]
  for column in cache[first_contract]:
    if isinstance(cache[first_contract][column], dict):
      for subcolumn in cache[first_contract][column]:
        header.append(column+"_"+subcolumn)
    else:
      header.append(column)
  csv_writer.writerow(header)
  for registered_address in cache:
    row = [registered_address]
    for column in cache[registered_address].values():
      if isinstance(column, dict):
        for subcolumn in column.values():
          row.append(subcolumn)
      else:
        row.append(column)
    csv_writer.writerow(row)
  csv_file.close()

parser = argparse.ArgumentParser()
parser.add_argument('-o', '--overwrite-cache', action='store_true', help='Overwrite cache file')
parser.add_argument("-t", "--timestamp", type=str, help="fetch balances ending at this timestamp")
args = parser.parse_args()

# HTTPProvider:
w3 = Web3(Web3.HTTPProvider(eth_node_api))

if args.timestamp:
  timestamp = int(args.timestamp)
  block = get_block(timestamp)
else:
  timestamp = int(time.time())
  block = 'latest'

create_emp_event_hash = w3.keccak(text=EMP_CREATE)
create_perp_event_hash = w3.keccak(text=PERP_CREATE)
create_jarvis_event_hash = w3.keccak(text=JARVIS_CREATE)
create_jarvis_self_event_hash = w3.keccak(text=JARVIS_SELF_CREATE)

token_abi = load_abi(weth_address)

finder_contract = load_contract(finder_address)

registry_address = finder_contract.functions.getImplementationAddress('0x'+'Registry'.encode("utf-8").hex()).call()

registry_contract = load_contract(registry_address)

all_registered_contracts = registry_contract.functions.getAllRegisteredContracts().call()

if args.overwrite_cache:
  cache = {}
else:
  try:
    with open(cache_file, 'r') as f:
      cache = json.load(f)
  except FileNotFoundError:
    cache = {}

for registered_address in all_registered_contracts:
  if registered_address in cache:
    print_cache(registered_address)
    continue
  creation = load_creation(registered_address)
  if creation and creation["deployer"]:
    if creation["create_time"] > timestamp:
      print('Contract %s created after requested timestamp, stopping' % (registered_address))
      break
    contract_type = creation["type"]
    if contract_type == "emp":
      if emp_abi == []:
        emp_abi = load_abi(registered_address)
      contract_abi = emp_abi
    elif contract_type == "perp":
      if perp_abi == []:
        perp_abi = load_abi(registered_address)
      contract_abi = perp_abi
    elif contract_type == "jarvis_v1":
      if jarvis_v1_abi == []:
        jarvis_v1_abi = load_abi(registered_address)
      contract_abi = jarvis_v1_abi
    elif contract_type == "jarvis_v2":
      if jarvis_v2_abi == []:
        jarvis_v2_abi = load_abi(registered_address)
      contract_abi = jarvis_v2_abi
    elif contract_type == "jarvis_self":
      if jarvis_self_abi == []:
        jarvis_self_abi = load_abi(registered_address)
      contract_abi = jarvis_self_abi
    else:
      continue

    registered_contract = w3.eth.contract(address=registered_address, abi=contract_abi)

    collateral_address = registered_contract.functions.collateralCurrency().call()
    collateral_token = w3.eth.contract(address=collateral_address, abi=token_abi)
    collateral_symbol = collateral_token.functions.symbol().call()
    collateral_decimals = collateral_token.functions.decimals().call()

    collateral_locked = registered_contract.functions.pfc().call(block_identifier=block)[0] / 10 ** collateral_decimals

    synth_address = registered_contract.functions.tokenCurrency().call()
    synth_token = w3.eth.contract(address=synth_address, abi=token_abi)
    synth_symbol = synth_token.functions.symbol().call()
    synth_decimals = synth_token.functions.decimals().call()
    synth_minted = synth_token.functions.totalSupply().call(block_identifier=block) / 10 ** synth_decimals

    if contract_type == 'jarvis_v1' or contract_type == 'jarvis_v2' or contract_type == 'jarvis_self':
      liquidatable_data = registered_contract.functions.liquidatableData().call(block_identifier=block)
      collateral_requirement = liquidatable_data[2][0] / 10 ** DECIMALS
      liquidation_liveness = liquidatable_data[1]
    else:
      collateral_requirement = registered_contract.functions.collateralRequirement().call() / 10 ** DECIMALS

    if contract_type == 'emp':
      emp_state = EMP_STATES[registered_contract.functions.contractState().call(block_identifier=block)]
      expiration = int(registered_contract.functions.expirationTimestamp().call())
    else:
      emp_state = None
      expiration = None

    if contract_type == 'jarvis_v1':
      position_manager_data = registered_contract.functions.positionManagerData().call(block_identifier=block)
      price_identifier = position_manager_data[1].strip(b'\x00').decode()
      withdrawal_liveness = position_manager_data[2]
      min_sponsor_tokens = position_manager_data[3][0]
    elif contract_type == 'jarvis_self' or contract_type == 'jarvis_v2':
      position_manager_data = registered_contract.functions.positionManagerData().call(block_identifier=block)
      price_identifier = position_manager_data[2].strip(b'\x00').decode()
      withdrawal_liveness = position_manager_data[3]
      min_sponsor_tokens = position_manager_data[4][0]
    else:
      price_identifier = registered_contract.functions.priceIdentifier().call().strip(b'\x00').decode()
      min_sponsor_tokens = registered_contract.functions.minSponsorTokens().call() / 10 ** synth_decimals
      liquidation_liveness = registered_contract.functions.liquidationLiveness().call()
      withdrawal_liveness = registered_contract.functions.withdrawalLiveness().call()

    cache[registered_address] = {
        'type': contract_type,
        'deployer': creation['deployer'],
        'deployed_at': creation['create_time'],
        'collateral_requirement': collateral_requirement,
        'contract_state': emp_state,
        'expires_at': expiration,
        'price_id': price_identifier,
        'min_sponsor_tokens': min_sponsor_tokens,
        'liquidation_liveness': liquidation_liveness,
        'withdrawal_liveness': withdrawal_liveness,
        'collateral_address': collateral_address,
        'collateral_address': collateral_address,
        'collateral_symbol': collateral_symbol,
        'collateral_decimals': collateral_decimals,
        'collateral_locked': collateral_locked,
        'synth_address': synth_address,
        'synth_symbol': synth_symbol,
        'synth_decimals': synth_decimals,
        'synth_minted': synth_minted,
    }
    print_cache(registered_address)
  else:
    print('Unrecognized contract type: %s' % (registered_address))

with open(cache_file, 'w') as f:
  json.dump(cache, f)

write_csv()
