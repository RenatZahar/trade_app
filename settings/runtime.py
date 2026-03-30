import os
from dotenv import load_dotenv

load_dotenv()

rpc_user = os.getenv('RPC_USER')
rpc_password = os.getenv('RPC_PASSWORD')
rpc_host = os.getenv('RPC_HOST')
rpc_port = os.getenv('RPC_PORT')

BITCOIN_CORE_PROCESS_NAME = 'bitcoin-qt.exe'


