# === Config ===
import os
# from langchain.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI
# import getpass

#github client
GITHUB_TOKEN = os.getenv("greenqloudfingrainedtoken")

#Prometheus metrics client
PROMETHEUS_CLIENT_ID=os.getenv("prometheus_client_id")

#Prometheus alert rule groups
SUBSCRIPTION = "19998cf7-a1b7-4c69-8daf-1f026e397d66"
RESOURCEGROUP = "anf.dc.mgmt.eastus-stage.rg"
APIVERSION = "2023-03-01"
