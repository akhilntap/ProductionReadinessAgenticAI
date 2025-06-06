# from langchain.agents import initialize_agent, Tool
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
# from langchain.chat_models import ChatOpenAI
from langchain_openai import ChatOpenAI
from typing import Optional, TypedDict, Annotated
from pydantic.v1 import BaseModel, Field
import operator
# from langchain.prompts import PromptTemplate
import requests
from github import Github
import os
import getpass
from bandit.core import manager, config
from azure.identity import ManagedIdentityCredential
# import config
import pandas as pd
import ollama
import tempfile
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langchain.chat_models import init_chat_model
from langchain_core.messages import convert_to_messages

# model_to_use = "llama3.3:latest"



# === Tool 1: GitHub PR Fetcher ===
def fetch_pr_diff_and_metadata(repo_name, pr_number, github_token=config.GITHUB_TOKEN):
    """
    Fetch pull request metadata and diff from GitHub.

    Args:
        repo_name (str): The full repository name (e.g., "owner/repo").
        pr_number (int): The pull request number.
        github_token (str): GitHub personal access token.

    Returns:
        dict: Dictionary with keys 'pr', 'pr_title', 'pr_body', 'diff_text'.
    """
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    pr_title = pr.title
    pr_body = pr.body
    diff_response = requests.get(
        f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}",
        headers={
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3.diff"
        }
    )
    diff_text = diff_response.text
    return diff_text
class prrepo(BaseModel):
    repo_name: str = Field(description="Repo to execute")
    pr_number: int = Field(description="PR number to execute")
@tool(args_schema = prrepo)
def fetchprdiff(repo_name: str, pr_number: int) -> str:
  """Returns the result of diff text in a PR"""
  return fetch_pr_diff_and_metadata(repo_name, pr_number, github_token=config.GITHUB_TOKEN)


# === Tool 1: GitHub File Fetcher ===
def get_file_context(filename, ref="master"):
    g = Github(config.GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    try:
        contents = repo.get_contents(filename, ref=ref)
        return contents.decoded_content.decode('utf-8', errors='ignore')
    except Exception as e:
        return f"Error fetching file {filename}: {e}"
# Tool for langrgaph

class filecontent(BaseModel):
    filename: str = Field(description="Get full contents of file")
@tool(args_schema = filecontent)
def file_fetch_tool(filename: str, ref: str = "master") -> str:
   """
    Fetch full content of a given file from the repo for additional context.
    """
   return get_file_context(filename, ref="master")



# === Tool 2: Prometheus metrics fetcher ===
def get_prometheus_metrics(prometheus_url="https://prometheusmdmeastus-stage-060d.eastus.prometheus.monitor.azure.com"):
    try:
        credential = ManagedIdentityCredential(client_id=config.PROMETHEUS_CLIENT_ID)
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
# Tool for LangGraph
class prometheusmetricsurl(BaseModel):
    prometheus_url: str = Field(description="Get full contents of file")
@tool(args_schema = prometheusmetricsurl)
def prometheus_metrics_fetch_tool(prometheus_url: str) -> list:
    """
    Fetch all the prometheus metrics from azure monitor workspace to get context for observability.
    """
    return get_prometheus_metrics(prometheus_url)




# === Tool 3: Prometheus alerts rule groups fetcher ===
def get_prometheus_rule_groups(subscription_id, resource_group=config.RESOURCEGROUP, client_id=config.PROMETHEUS_CLIENT_ID):
    """
    Fetch Prometheus rule groups from Azure Monitor and return as a DataFrame.

    # Args:
    #     subscription_id (str): Azure subscription ID.
    #     resource_group (str): Azure resource group name.
    #     api_version (str): API version to use.
    #     client_id (str): Client ID for Managed Identity.

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
        f"/prometheusRuleGroups?api-version=2023-03-01"
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
# Tool for LangGraph
class prometheusmetricsurla(BaseModel):
    subscription_id: str = Field(description="subscription id")
@tool(args_schema = prometheusmetricsurla)
def prometheus_alert_rule_group_fetch_tool(subscription_id: str) -> list:
    """
    Fetch all the prometheus metrics from azure monitor workspace to get context for observability.
    """
    return get_prometheus_rule_groups(subscription_id)

# # === Tool 4: Bandit Code Security checker ===
# def check_code_security(file_path):
#     """
#     Check a Python file for security vulnerabilities using Bandit.

#     :param file_path: Path to the Python file to analyze
#     :return: Bandit report as a string
#     """
#     # Load Bandit configuration
#     bandit_config = config.BanditConfig()

#     # Initialize Bandit manager
#     bandit_manager = manager.BanditManager(bandit_config, "file", False)

#     # Run Bandit on the specified file
#     bandit_manager.discover_files([file_path])
#     bandit_manager.run_tests()

#     # Generate and return the report
#     issues = bandit_manager.get_issue_list()
#     if not issues:
#         return "No high-level vulnerabilities found. Checking for lower-level issues..."

#     # If no high-level issues, check for lower-level issues
#     lower_level_issues = []
#     for issue in issues:
#         if issue.severity.lower() in ['low', 'medium']:
#             lower_level_issues.append(str(issue))

#     if lower_level_issues:
#         return "\n".join(lower_level_issues)
#     else:
#         return "No vulnerabilities found, including lower-level issues."
# # Tool wrapper for LangChain
# class banditsecurity(BaseModel):
#     file_path: str = Field(description="Get path of file to execute")
# @tool(args_schema = banditsecurity)
# def bandit_security_checker_tool(file_path: str) -> str:
#     """
#     Check security of a python code using bandit library.
#     """
#     return check_code_security(file_path)



# === Tool 4: Bandit Code Security checker for PR files ===
def check_pr_files_security(repo_name, pr_number):
    """
    Fetch changed files in a PR, get their content, and check for security vulnerabilities using Bandit.

    :param repo_name: Repository name (e.g., "owner/repo")
    :param pr_number: Pull request number
    :return: Bandit report as a string
    """
    g = Github(config.GITHUB_TOKEN)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    changed_files = [f.filename for f in pr.get_files() if f.filename.endswith('.py')]
    if not changed_files:
        return "No Python files changed in this PR."

    results = []
    for filename in changed_files:
        code = get_file_context(filename, ref=pr.head.ref)
        # Write code to a temporary file for Bandit to scan
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        # Run Bandit
        bandit_config = config.BanditConfig()
        bandit_manager = manager.BanditManager(bandit_config, "file", False)
        bandit_manager.discover_files([tmp_path])
        bandit_manager.run_tests()
        issues = bandit_manager.get_issue_list()
        if not issues:
            results.append(f"{filename}: No high-level vulnerabilities found.")
        else:
            lower_level_issues = []
            for issue in issues:
                if issue.severity.lower() in ['low', 'medium']:
                    lower_level_issues.append(str(issue))
            if lower_level_issues:
                results.append(f"{filename}:\n" + "\n".join(lower_level_issues))
            else:
                results.append(f"{filename}: No vulnerabilities found, including lower-level issues.")
    return "\n\n".join(results)

class banditprsecurity(BaseModel):
    repo_name: str = Field(description="Repo to execute")
    pr_number: int = Field(description="PR number to execute")
@tool(args_schema = banditprsecurity)
def bandit_pr_security_checker_tool(repo_name: str, pr_number: int) -> str:
    """
    Check security of all Python files changed in a PR using the bandit library.
    """
    return check_pr_files_security(repo_name, pr_number)



def pretty_print_message(message, indent=False):
    pretty_message = message.pretty_repr(html=True)
    if not indent:
        print(pretty_message)
        return

    indented = "\n".join("\t" + c for c in pretty_message.split("\n"))
    print(indented)


def pretty_print_messages(update, last_message=False):
    is_subgraph = False
    if isinstance(update, tuple):
        ns, update = update
        # skip parent graph updates in the printouts
        if len(ns) == 0:
            return

        graph_id = ns[-1].split(":")[0]
        print(f"Update from subgraph {graph_id}:")
        print("\n")
        is_subgraph = True

    for node_name, node_update in update.items():
        update_label = f"Update from node {node_name}:"
        if is_subgraph:
            update_label = "\t" + update_label

        print(update_label)
        print("\n")

        messages = convert_to_messages(node_update["messages"])
        if last_message:
            messages = messages[-1:]

        for m in messages:
            pretty_print_message(m, indent=is_subgraph)
        print("\n")








