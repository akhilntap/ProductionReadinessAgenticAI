import streamlit as st
from streamlit_extras.add_vertical_space import add_vertical_space
from PIL import Image
import os
import functions
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent, create_supervisor

from functions import (
    fetchprdiff,
    file_fetch_tool,
    prometheus_metrics_fetch_tool,
    prometheus_alert_rule_group_fetch_tool,
    bandit_pr_security_checker_tool,
)

# Warm up model
os.system('ollama run llama3.3:latest what is water short answer')
model_to_use = ChatOllama(model="llama3.3:latest", temperature=0.1)

# Sidebar for repo/pr input
REPO_NAME = st.sidebar.text_input("Repository Name", value="greenqloud/cloud-backup-service")
PULL_REQUEST_NUMBER = st.sidebar.number_input("Pull Request Number", value=1853, step=1)

# Define agents
observability_agent = create_react_agent(
    model=model_to_use,
    tools=[fetchprdiff, file_fetch_tool, prometheus_metrics_fetch_tool, prometheus_alert_rule_group_fetch_tool],
    prompt=(
        "You are a observability agent reading the code to analyze gaps in observability.\n\n"
        "INSTRUCTIONS:\n"
        """- Assist ONLY with following observability-related tasks
        - Are there actionable alerts identified for the feature? Are there Runbooks for the actionable alerts? Do we have TSGs attached to the alert? use prometheus_alert_rule_group_fetch_tool to see if there are already alert rules related to this change
        - Are there metrics to monitor dependencies and exception handling on components, infrastructure and features so that SRE can create alerts to reduce TTD? Use prometheus_metrics_fetch_tool to see if there are metrics related to the change 
        - Are there CorrelationIDs established in logs to derive error lineage across various components?
        - Can the feature/service support changing log levels for troubleshooting purposes?
        - Are there critical log lines that we need to get alerted upon?"""
        "- After you're done with your tasks, respond to the supervisor directly\n"
        "- Respond ONLY with the results of your work, do NOT include ANY other text."
    ),
    name="observability_agent",
)

security_agent = create_react_agent(
    model=model_to_use,
    tools=[fetchprdiff, file_fetch_tool, bandit_pr_security_checker_tool],
    prompt=(
        "You are a security agent reading the code to analyze security vulnerabilities.\n\n"
        "INSTRUCTIONS:\n"
        """- Assist ONLY with following security-related tasks
        - All sensitive log lines are masked appropriately?
        - Are all secrets encrypted at rest and in transit?
        - Are all data encrypted at rest and in transit?
        - Are we using distroless/mariner base image/s?"""
        "If the diff is unclear, use the FileFetcher tool to retrieve extra context of the file.If the file has import from custom modules use the file_fetch_tool tool to retreive the file"
        "- After you're done with your tasks, respond to the supervisor directly\n"
        "- Respond ONLY with the results of your work, do NOT include ANY other text."
    ),
    name="security_agent",
)

database_agent = create_react_agent(
    model=model_to_use,
    tools=[fetchprdiff, file_fetch_tool],
    prompt=(
        "You are a database agent reading the code to analyze gaps from a database perscpective.\n\n"
        "INSTRUCTIONS:\n"
        """- Assist ONLY with following database-related tasks
        - What is the expected growth rate?
        - What happens to the service if the database is down?
        - Can the service park the data elsewhere and complete the API transaction to protect the customer from database failures?
        - Does the service have any caching solution to sustain a relational database failure ( if any relational databases are used )
        - Can the service sustain an extended maintenance period of 2 minutes? What is the application behavior when the database is unavailable for 2 minutes during a maintenance window?"""
        "If the diff is unclear, use the FileFetcher tool to retrieve extra context of the file.If the file has import from custom modules use the file_fetch_tool tool to retreive the file"
        "- After you're done with your tasks, respond to the supervisor directly\n"
        "- Respond ONLY with the results of your work, do NOT include ANY other text."
    ),
    name="database_agent",
)

quality_agent = create_react_agent(
    model=model_to_use,
    tools=[fetchprdiff, file_fetch_tool],
    prompt=(
        "You are a quality agent reading the code to analyze gaps from a code quality perscpective.\n\n"
        "INSTRUCTIONS:\n"
        """- Assist ONLY with following code quality related tasks
        - Code Quality: Claritym modularitym readability, naming conventions, comments DRY principle, error handling
        - Performance: time/space complexity, resource usage, scalability
        - Readability: Error handling, logging, robustness in edge cases
        - Best Practices: adherence to language/framework conventions, proper usage of tools/libraries"""
        "If the diff is unclear, use the FileFetcher tool to retrieve extra context of the file.If the file has import from custom modules use the file_fetch_tool tool to retreive the files from the repo"
        "- After you're done with your tasks, respond to the supervisor directly\n"
        "- Respond ONLY with the results of your work, do NOT include ANY other text."
    ),
    name="quality_agent",
)

supervisor = create_supervisor(
    model=model_to_use,
    agents=[observability_agent, security_agent, database_agent, quality_agent],
    prompt=(
        "You are a supervisor managing two agents:\n"
        "- a observability agent. Assign observability-related tasks to this agent\n"
        "- a security agent. Assign security-related tasks to this agent\n"
        "- a database agent. Assign database-related tasks to this agent\n"
        "- a quality agent. Assign quality-related tasks to this agent\n"
        "Assign work to one agent at a time, do not call agents in parallel.\n"
        "Do not do any work yourself."
    ),
    add_handoff_back_messages=True,
    output_mode="full_history",
).compile()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! Ask me about a pull request and I'll analyze it for observability, security, database, and quality requirements."}
    ]

st.title("Multi-Agent PR Review Chatbot")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Ask about a pull request..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare messages for supervisor
    messages = [
        {"role": "user", "content": f"{prompt}\n\nRepository: {REPO_NAME}\nPull Request: {PULL_REQUEST_NUMBER}"}
    ]

    # Stream supervisor response
    response = ""
    for chunk in supervisor.stream({"messages": messages}):
        # Get the latest supervisor message
        supervisor_msgs = chunk["supervisor"]["messages"]
        if supervisor_msgs:
            last_msg = supervisor_msgs[-1]["content"]
            response = last_msg
            # Display streaming response
            with st.chat_message("assistant"):
                st.markdown(response)
    # Add assistant message to history
    st.session_state.messages.append({"role": "assistant", "content": response})