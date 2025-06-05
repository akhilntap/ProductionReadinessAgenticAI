import os
import getpass # to get the current user
from langchain_openai import ChatOpenAI
# from langchain.chains import ConversationChain
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
from pydantic.v1 import BaseModel, Field
from typing import Optional, TypedDict, Annotated
import operator
from semantic_router.utils.function_call import FunctionSchema
import csv
from bandit.core import manager, config
import requests
import json
from azure.identity import ManagedIdentityCredential
import pandas as pd


def read_python_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        return "Error: File not found."
    
def read_csv_file(file_path):
    try:
        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            return [row for row in reader]
    except FileNotFoundError:
        return "Error: File not found."
 
def get_prometheus_metrics(prometheus_url):
    try:
        credential = ManagedIdentityCredential(client_id=os.getenv("prometheus_client_id"))
        token = credential.get_token("https://data.monitor.azure.com").token
        headers = {
            "Authorization": f"Bearer {token}"
        }
        response = requests.get(f"{prometheus_url}/api/v1/label/__name__/values", headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'success':
            return data.get('data', [])
        else:
            print(f"Error from Prometheus API: {data}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"HTTP request failed: {e}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def get_prometheus_rule_groups(subscription_id, resource_group, api_version, client_id):
    """
    Fetch Prometheus rule groups from Azure Monitor and return as a DataFrame.

    Args:
        subscription_id (str): Azure subscription ID.
        resource_group (str): Azure resource group name.
        api_version (str): API version to use.
        client_id (str): Client ID for Managed Identity.

    Returns:
        pd.DataFrame: DataFrame containing rule group details, or None if the request fails.
    """
    # Get token using Managed Identity (DefaultAzureCredential)
    credential = ManagedIdentityCredential(client_id=client_id)
    token = credential.get_token("https://management.azure.com/.default").token

    # Construct API URL for listing all rule groups
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/resourceGroups/{resource_group}/providers/Microsoft.AlertsManagement"
        f"/prometheusRuleGroups?api-version={api_version}"
    )

    # Set headers with the bearer token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Make the GET request to Azure Monitor
    response = requests.get(url, headers=headers)

    # Check and process response
    if response.status_code == 200:
        data = response.json()
        rule_groups = []
        for rule_group in data.get("value", []):
            rule_groups.append({
                "Name": rule_group['name'],
                "Location": rule_group.get('location'),
                "Description": rule_group.get('properties', {}).get('description'),
                "Rules": rule_group.get('properties', {}).get('rules')
            })
        return pd.DataFrame(rule_groups)
    else:
        print(f"Failed to fetch rule groups. Status Code: {response.status_code}")
        print(response.text)
        return None

def check_code_security(file_path):
    """
    Check a Python file for security vulnerabilities using Bandit.

    :param file_path: Path to the Python file to analyze
    :return: Bandit report as a string
    """
    # Load Bandit configuration
    bandit_config = config.BanditConfig()

    # Initialize Bandit manager
    bandit_manager = manager.BanditManager(bandit_config, "file", False)

    # Run Bandit on the specified file
    bandit_manager.discover_files([file_path])
    bandit_manager.run_tests()

    # Generate and return the report
    issues = bandit_manager.get_issue_list()
    if not issues:
       return "No high-level vulnerabilities found. Checking for lower-level issues..."

    # If no high-level issues, check for lower-level issues
    lower_level_issues = []
    for issue in issues:
       if issue.severity.lower() in ['low', 'medium']:
          lower_level_issues.append(str(issue))

    if lower_level_issues:
        return "\n".join(lower_level_issues)
    else:
        return "No vulnerabilities found, including lower-level issues."
    
class codepath(BaseModel):
    path: str = Field(description="code path to execute")

class csvpath(BaseModel):
    path: str = Field(description="CSV file path to read")

class prometheus(BaseModel):
   path: str = Field(description="Prometheus URL to get metrics")

class prometheusrules(BaseModel):
   path: str = Field(description="Prometheus parameters to get metrics")

@tool(args_schema = codepath)
def read_python(path: str) -> str:
  """Returns the result of code path execution"""
  return read_python_file(path)

@tool(args_schema=csvpath)
def read_csv(path: str) -> list:
    """Returns the content of a CSV file as a list of rows"""
    return read_csv_file(path)

@tool(args_schema=prometheus)
def get_metrics(path: str) -> list:
    """Returns the prometheus metrics"""
    return get_prometheus_metrics(path)

@tool(args_schema=prometheusrules)
def get_rules(path: str) -> list:
    """Returns the prometheus rule groups"""
    return get_prometheus_rule_groups()

@tool(args_schema=codepath)
def check_code(path: str) -> str:
    """Returns the result of code path execution"""
    return check_code_security(path)

# Define the agent state
class AgentState(TypedDict):
   messages: Annotated[list[AnyMessage], operator.add]


# create the function calling schema for ollama
execute_query_schema = FunctionSchema(read_python_file).to_ollama()
# execute_query_schema["function"]["parameters"]["properties"]["description"] = None
execute_query_schema["function"]["parameters"]["properties"]["description"] = None

# create the function calling schema for read_csv_file
read_csv_schema = FunctionSchema(read_csv_file).to_ollama()
read_csv_schema["function"]["parameters"]["properties"]["description"] = None

class codeAgent:
  # initialising the object
  def __init__(self, model, tools, system_prompt = ""):
    self.system_prompt = system_prompt

    # initialising graph with a state 
    graph = StateGraph(AgentState)

    # adding nodes 
    graph.add_node("llm", self.call_llm)
    graph.add_node("function", self.execute_function)
    graph.add_conditional_edges(
      "llm",
      self.exists_function_calling,
      {True: "function", False: END}
    )
    graph.add_edge("function", "llm")

    # setting starting point
    graph.set_entry_point("llm")

    self.graph = graph.compile()
    self.tools = {t.name: t for t in tools}
    self.model = model.bind_tools(tools)

  def call_llm(self, state: AgentState):
    messages = state['messages']
    # adding system prompt if it's defined
    if self.system_prompt:
        messages = [SystemMessage(content=self.system_prompt)] + messages

    # calling LLM
    message = self.model.invoke(messages)

    return {'messages': [message]}
  
  def execute_function(self, state: AgentState):
    tool_calls = state['messages'][-1].tool_calls

    results = []
    for tool in tool_calls:
      # checking whether tool name is correct
      if not tool['name'] in self.tools:
        # returning error to the agent 
        result = "Error: There's no such tool, please, try again" 
      else:
        # getting result from the tool
        result = self.tools[tool['name']].invoke(tool['args'])

      results.append(
        ToolMessage(
          tool_call_id=tool['id'], 
          name=tool['name'], 
          content=str(result)
        )
    )
    return {'messages': results}
  
  def exists_function_calling(self, state: AgentState):
    result = state['messages'][-1]
    return len(result.tool_calls) > 0


def analyze_observability(model: str, human_message: str):
  model = ChatOpenAI(model_name      = model,
         openai_api_base = os.getenv('aifoundrygpt40endpoint'),
         openai_api_key  = os.getenv('aifoundrygpt40key')
                    )
  """
  Analyzes a given file for observability requirements based on the content of the human message.

  Args:
    human_message (str): The message containing details about the file and its type.

  Returns:
    dict: The result of the analysis.
  """
  if "observability" in human_message.lower():
    prompt = '''You are a senior expert in reviewing code for observability. The best one that exists.
    Your goal is to analyze the code on the following questions 
    1. Are there actionable alerts identified for the feature? Are there Runbooks for the actionable alerts? Do we have TSGs attached to the alert? Feel free to use the tools to get existing alerts, paramaters to use are subscription_id= "19998cf7-a1b7-4c69-8daf-1f026e397d66", resource_group = "anf.dc.mgmt.eastus-stage.rg", api_version="2023-03-01", client_id=os.getenv("prometheus_client_id")
    2. Add metrics to monitor dependencies and exception handling on components, infrastructure and features so that SRE can create alerts to reduce TTD? Feel free to use the tools to get existing metrics in the prometheus. the query endpoint for monitor workspace is https://prometheusmdmeastus-stage-060d.eastus.prometheus.monitor.azure.com
    3. Are there CorrelationIDs established in logs to derive error lineage across various components?
    4. Can the feature/service support changing log levels for troubleshooting purposes?
    5. Are there critical log lines that we need to get alerted upon?
    Provide response in the format as follows: {question: response}
    '''
    tools = [read_python, get_metrics, get_rules]
  elif "log" in human_message.lower():
    prompt = '''You are a senior expert in for observability. The best one that exists.
    Your goal is to analyze the logs on the following questions 
    1. What are the top failures from the logs?
    2. Based on the logs, what are the top 5 errors that need to be alerted on?
    3. What metrics should I need to alert for these logs?
    4. What should I alert on from the logs?
    Provide response in the format as follows: {question: response}
    '''
    tools = [read_csv]
  elif "security vulnerabilities" in human_message.lower():
    prompt = '''You are a senior expert in for security. The best one that exists. Use the check_code function to check the code for security vulnerabilities to give additional details
    Your goal is to analyze the code on the following questions 
    1. All sensitive log lines are masked appropriately?
    2. Are all secrets encrypted at rest and in transit?
    3. Are all data encrypted at rest and in transit?
    4. Are we using distroless/mariner base image/s?
    Provide response in the format as follows: {question: response}
    '''
    tools = [check_code]
     
  else:
    raise ValueError("Invalid human_message. Must mention 'code' or 'log' or 'Security Vulnerabilities'.")

  doc_agent = codeAgent(model, tools, system_prompt=prompt)
  messages = [HumanMessage(content=human_message)]
  result = doc_agent.graph.invoke({"messages": messages})
  return result['messages'][-1].content


