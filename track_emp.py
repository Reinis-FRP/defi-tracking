#!/usr/bin/env python3

import datetime
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

# Possible EMP contract states:
EMP_STATES = ('Open', 'ExpiredPriceRequested', 'ExpiredPriceReceived')

# Default scaling:
DECIMALS = 18

# Use the same ABI for all EMP contracts (will fetch it for the first EMP discovered):
emp_abi = []

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

def get_deployer(tx):
  tx_logs = w3.eth.getTransactionReceipt(tx["hash"]).logs
  if tx_logs == []:
    return None
  for event in tx_logs:
    if event["topics"][0] == create_event_hash:
      if event["address"].lower() == tx["from"]:
        return w3.toChecksumAddress('0x'+event["topics"][2].hex()[26:])
  return None

def load_creation(contract_address):
  creation_tx = first_internal(contract_address)
  if creation_tx:
    return {'create_time': int(creation_tx["timeStamp"]), 'deployer': get_deployer(creation_tx)}
  else:
    return None

# HTTPProvider:
w3 = Web3(Web3.HTTPProvider('https://eth-mainnet.alchemyapi.io/v2/'+alchemy_key))

create_event_hash = w3.keccak(text=EMP_CREATE)

token_abi = load_abi(weth_address)

finder_contract = load_contract(finder_address)

registry_address = finder_contract.functions.getImplementationAddress('0x'+'Registry'.encode("utf-8").hex()).call()

registry_contract = load_contract(registry_address)

all_registered_contracts = registry_contract.functions.getAllRegisteredContracts().call()

for registered_address in all_registered_contracts:
  creation = load_creation(registered_address)
  if creation and creation["deployer"]:
    if emp_abi == []:
      emp_abi = load_abi(registered_address)

    print('EMP contract: %s' % (registered_address))
    print('  Deployed at: %s UTC' % (datetime.datetime.utcfromtimestamp(creation["create_time"])))
    print('  Deployer: %s' % (creation["deployer"]))

    emp_contract = w3.eth.contract(address=registered_address, abi=emp_abi)

    collateral_address = emp_contract.functions.collateralCurrency().call()
    collateral_token = w3.eth.contract(address=collateral_address, abi=token_abi)
    collateral_symbol = collateral_token.functions.symbol().call()
    collateral_decimals = collateral_token.functions.decimals().call()

    print('  Collateral: %s' % (collateral_symbol))

    synth_address = emp_contract.functions.tokenCurrency().call()
    synth_token = w3.eth.contract(address=synth_address, abi=token_abi)
    synth_symbol = synth_token.functions.symbol().call()
    synth_decimals = synth_token.functions.decimals().call()

    print('  Synth token: %s' % (synth_symbol))

    collateral_requirement = emp_contract.functions.collateralRequirement().call() / 10 ** DECIMALS
    print('  Collateral requirement: %f' % (collateral_requirement))

    emp_state = EMP_STATES[emp_contract.functions.contractState().call()]
    print('  Contract state: %s' % (emp_state))

    expiration = int(emp_contract.functions.expirationTimestamp().call())
    print('  Expires at: %s UTC' % (datetime.datetime.utcfromtimestamp(expiration)))

    price_identifier = emp_contract.functions.priceIdentifier().call().strip(b'\x00').decode()
    print('  Price identifier: %s' % (price_identifier))

    min_sponsor_tokens = emp_contract.functions.minSponsorTokens().call() / 10 ** synth_decimals
    print('  Minimum sponsor tokens %f' % (min_sponsor_tokens))

    liquidation_liveness = emp_contract.functions.liquidationLiveness().call()
    print('  Liquidation liveness: %f hours' % (liquidation_liveness / 3600))

    withdrawal_liveness = emp_contract.functions.withdrawalLiveness().call()
    print('  Withdrawal liveness: %f hours' % (withdrawal_liveness / 3600))

#    print(registered_address, datetime.datetime.utcfromtimestamp(creation["create_time"]), creation["deployer"], collateral_symbol, synth_symbol, collateral_requirement, emp_state, datetime.datetime.utcfromtimestamp(expiration), liquidation_liveness / 3600, min_sponsor_tokens, price_identifier, withdrawal_liveness / 3600)
 
