# === Config ===
import os
# from langchain.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI
import getpass

GITHUB_TOKEN = os.getenv("greenqloudfingrainedtoken")
OPENAI_ENDPOINT = os.getenv('proxyllmendpoint')
OPENAI_API_KEY = os.getenv('proxyllmuserkey')

# === LangChain LLM ===
#  getting the required ssl certificates
pem_path = "/opt/homebrew/etc/openssl@3/cert.pem"
# Ensure the environment variables are set before making the API call
os.environ['REQUESTS_CA_BUNDLE'] = pem_path
os.environ['SSL_CERT_FILE'] = pem_path


llm = ChatOpenAI(model_name      = "gpt-4o-mini",
                 openai_api_base = OPENAI_ENDPOINT,
                 openai_api_key  = OPENAI_API_KEY,
                 model_kwargs    = {'user': getpass.getuser() },
                 temperature = 0.1)