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

def get_block(timestamp):
  API_ENDPOINT = etherscan_api+"?module=block&action=getblocknobytime&closest=before&timestamp="+str(timestamp)+"&apikey="+etherscan_key
  r = requests.get(url = API_ENDPOINT)
  response = r.json()
  return int(response["result"])

parser = argparse.ArgumentParser()
parser.add_argument("-t", "--timestamp", type=int, help="get the latest block for this timestamp")
parser.add_argument("-b", "--block", type=int, help="get the block timestamp")
args = parser.parse_args()

# HTTPProvider:
w3 = Web3(Web3.HTTPProvider('https://eth-mainnet.alchemyapi.io/v2/'+alchemy_key))

if args.block:
  block = args.block
  timestamp = w3.eth.getBlock(block).timestamp
  r_timestamp = timestamp
elif args.timestamp:
  r_timestamp = args.timestamp
  block = get_block(r_timestamp)
  timestamp = w3.eth.getBlock(block).timestamp
else:
  block = w3.eth.blockNumber
  timestamp = w3.eth.getBlock(block).timestamp
  r_timestamp = int(time.time())

print('Requested timestamp: %d is %s UTC' % (r_timestamp, datetime.datetime.utcfromtimestamp(r_timestamp)))
print('Block timestamp: %d is %s UTC' % (timestamp, datetime.datetime.utcfromtimestamp(timestamp)))
print('Block number: %d' % (block))
