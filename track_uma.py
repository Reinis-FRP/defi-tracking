#!/usr/bin/env python3

import datetime
import json
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

# Possible EMP contract states:
EMP_STATES = ('Open', 'ExpiredPriceRequested', 'ExpiredPriceReceived')

# Default scaling:
DECIMALS = 18

# Use the same ABI for all EMP contracts (will fetch it for the first EMP discovered):
emp_abi = []

# Use the same ABI for all Perpetual contracts (will fetch it for the first Perpetual discovered):
perp_abi = []

# Use the same ABI for all Jarvis contracts (will fetch it for the first Jarvis discovered):
jarvis_abi = []

# Cache json file
cache_file = 'cache.json'

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
          if perp_event["topics"][0] == create_jarvis_event_hash: 
            return {'deployer': w3.toChecksumAddress('0x'+event["topics"][2].hex()[26:]), 'type': 'jarvis'}
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

# HTTPProvider:
w3 = Web3(Web3.HTTPProvider('https://eth-mainnet.alchemyapi.io/v2/'+alchemy_key))

create_emp_event_hash = w3.keccak(text=EMP_CREATE)
create_perp_event_hash = w3.keccak(text=PERP_CREATE)
create_jarvis_event_hash = w3.keccak(text=JARVIS_CREATE)

token_abi = load_abi(weth_address)

finder_contract = load_contract(finder_address)

registry_address = finder_contract.functions.getImplementationAddress('0x'+'Registry'.encode("utf-8").hex()).call()

registry_contract = load_contract(registry_address)

all_registered_contracts = registry_contract.functions.getAllRegisteredContracts().call()

try:
  with open(cache_file, 'r') as f:
    cache = json.load(f)
except FileNotFoundError:
  cache = {}

for registered_address in all_registered_contracts:
  if registered_address in cache:
    print(json.dumps(cache[registered_address], indent=2))
    continue
  creation = load_creation(registered_address)
  if creation and creation["deployer"]:
    contract_type = creation["type"]
    if contract_type == "emp":
      if emp_abi == []:
        emp_abi = load_abi(registered_address)
      contract_abi = emp_abi
    elif contract_type == "perp":
      if perp_abi == []:
        perp_abi = load_abi(registered_address)
      contract_abi = perp_abi
    elif contract_type == "jarvis":
      if jarvis_abi == []:
        jarvis_abi = load_abi(registered_address)
      contract_abi = jarvis_abi
    else:
      continue

    print('Contract: %s' % (registered_address))
    print('  Contract type: %s' % (contract_type))
    print('  Deployed at: %s UTC' % (datetime.datetime.utcfromtimestamp(creation["create_time"])))
    print('  Deployer: %s' % (creation["deployer"]))

    registered_contract = w3.eth.contract(address=registered_address, abi=contract_abi)

    collateral_address = registered_contract.functions.collateralCurrency().call()
    collateral_token = w3.eth.contract(address=collateral_address, abi=token_abi)
    collateral_symbol = collateral_token.functions.symbol().call()
    collateral_decimals = collateral_token.functions.decimals().call()

    print('  Collateral: %s' % (collateral_symbol))

    synth_address = registered_contract.functions.tokenCurrency().call()
    synth_token = w3.eth.contract(address=synth_address, abi=token_abi)
    synth_symbol = synth_token.functions.symbol().call()
    synth_decimals = synth_token.functions.decimals().call()

    print('  Synth token: %s' % (synth_symbol))

    if contract_type == 'jarvis':
      liquidatable_data = registered_contract.functions.liquidatableData().call()
      collateral_requirement = liquidatable_data[2][0] / 10 ** DECIMALS
      liquidation_liveness = liquidatable_data[1]
    else:
      collateral_requirement = registered_contract.functions.collateralRequirement().call() / 10 ** DECIMALS
    print('  Collateral requirement: %f' % (collateral_requirement))

    if contract_type == 'emp':
      emp_state = EMP_STATES[registered_contract.functions.contractState().call()]
      expiration = int(registered_contract.functions.expirationTimestamp().call())
      print('  Contract state: %s' % (emp_state))
      print('  Expires at: %s UTC' % (datetime.datetime.utcfromtimestamp(expiration)))
    else:
      emp_state = None
      expiration = None

    if contract_type == 'jarvis':
      position_manager_data = registered_contract.functions.positionManagerData().call()
      price_identifier = position_manager_data[1].strip(b'\x00').decode()
      withdrawal_liveness = position_manager_data[2]
      min_sponsor_tokens = position_manager_data[3][0]
    else:
      price_identifier = registered_contract.functions.priceIdentifier().call().strip(b'\x00').decode()
      min_sponsor_tokens = registered_contract.functions.minSponsorTokens().call() / 10 ** synth_decimals
      liquidation_liveness = registered_contract.functions.liquidationLiveness().call()
      withdrawal_liveness = registered_contract.functions.withdrawalLiveness().call()
    print('  Price identifier: %s' % (price_identifier))
    print('  Minimum sponsor tokens %f' % (min_sponsor_tokens))
    print('  Liquidation liveness: %f hours' % (liquidation_liveness / 3600))
    print('  Withdrawal liveness: %f hours' % (withdrawal_liveness / 3600))

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
        'collateral': {
            'address': collateral_address,
            'symbol': collateral_symbol,
            'decimals': collateral_decimals
        },
        'synth': {
            'address': synth_address,
            'symbol': synth_symbol,
            'decimals': synth_decimals,
        },
    }
  else:
    print('Other contract type: %s' % (registered_address))

with open(cache_file, 'w') as f:
  json.dump(cache, f)
