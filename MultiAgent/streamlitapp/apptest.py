import streamlit as st
from streamlit_feedback import streamlit_feedback
import requests
import os
import functions
from langchain_ollama import ChatOllama
from langgraph_supervisor import create_supervisor
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from io import StringIO
import sys
from langchain.schema import AIMessage
import ollama
import json
from datetime import datetime
import sys
import atexit
from io import StringIO


from functions import (
    fetchprdiff,
    file_fetch_tool,
    prometheus_metrics_fetch_tool,
    prometheus_alert_rule_group_fetch_tool,
    bandit_pr_security_checker_tool,
pretty_print_message, pretty_print_messages
)


def find_agent_chat_history_idx(agent_idx):
    count = -1
    for idx, msg in enumerate(st.session_state.chat_history):
        if msg['role'] == "agent":
            count += 1
            if count == agent_idx:
                return idx
    return None


# Warm up model
# os.system('ollama run llama3.3:latest what is water short answer')


st.set_page_config(page_title="PRR Agent APP", layout="wide")

# Variables to store selected values
REPO_NAME = None
PULL_REQUEST_NUMBER = None
pat_token = None

def get_prs(token, repo_full_name):
    headers = {"Authorization": f"token {token}"}
    response = requests.get(f"https://api.github.com/repos/{repo_full_name}/pulls", headers=headers)
    if response.status_code == 200:
        # Return list of (title, number) tuples
        return [(pr['title'], pr['number']) for pr in response.json()]
    return []
# def get_prs(token, repo_full_name):
#     headers = {"Authorization": f"token {token}"}
#     response = requests.get(f"https://api.github.com/repos/{repo_full_name}/pulls", headers=headers)
#     if response.status_code == 200:
#         return [pr['title'] for pr in response.json()]
#     return []

# Session state for login and selections
if 'token' not in st.session_state:
    st.session_state.token = ""
if 'repos' not in st.session_state:
    st.session_state.repos = []
if 'prs' not in st.session_state:
    st.session_state.prs = []
if 'selected_repo' not in st.session_state:
    st.session_state.selected_repo = None

def get_repos(token):
    headers = {"Authorization": f"token {token}"}
    repos = []
    page = 1
    while True:
        response = requests.get(
            f"https://api.github.com/user/repos?per_page=100&page={page}",
            headers=headers
        )
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        repos.extend([repo['full_name'] for repo in data])
        page += 1
    return repos



# Make the title sticky using custom CSS with improved contrast for visibility
st.markdown(
    """
    <style>
    .sticky-title {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        background: #111111; /* Even darker background for maximum contrast */
        z-index: 1000;
        padding-top: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #eee;
    }
    .sticky-title h1 {
        color: #ffffff !important; /* Pure white text for visibility */
        margin: 0;
        padding-left: 1.5rem;
        font-size: 2.2rem;
        letter-spacing: 1px;
        text-shadow: 0 1px 4px #000; /* Add subtle shadow for extra contrast */
    }
    .main, .block-container {
        margin-top: 90px !important; /* Ensure main content is not hidden behind sticky header */
    }
    </style>
    <div class="sticky-title">
        <h1>PRR Agent APP</h1>
    </div>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.header("User Info")
    user_name = st.text_input("Enter your name", key="user_name")
    email = st.text_input("Enter your email", key="email")
    if not user_name or not email:
        st.warning("Please enter your name and email to proceed.")
        st.stop()
    st.header("Model config")
    model_names = [model['model'] for model in ollama.list()['models']]
    # Default to "llama3.3:latest" if available, else first model
    default_model = "llama3.3:latest" if "llama3.3:latest" in model_names else model_names[0]
    selected_model = st.selectbox("Select Model", model_names, key="model_select", index=model_names.index(default_model))
    temperature = st.slider("Temperature", min_value=0.1, max_value=1.0, value=0.1, step=0.1, help="Controls the randomness of the model's responses. Lower values make it more deterministic, higher values make it more creative. Advised to keep it low for this app.")
    summarized_response = st.toggle("Summarized response", value=False, help="Show summarized vs full agent response")
    st.header("Github config")
    # PAT input
    token_input = st.text_input("Enter your GitHub Personal Access Token", type="password")
    if st.button("Load Repositories"):
        if token_input:
            st.session_state.token = token_input
            st.session_state.repos = get_repos(token_input)
            st.session_state.selected_repo = None
            st.session_state.prs = []
            if not st.session_state.repos:
                st.error("No repositories found or invalid token.")
        else:
            st.error("Please enter a token.")

    # Repository selection
    if st.session_state.repos:
        repo = st.selectbox("Select Repository", st.session_state.repos, key="repo_select")
        if repo != st.session_state.selected_repo:
            st.session_state.selected_repo = repo
            st.session_state.prs = get_prs(st.session_state.token, repo)

    # Pull Request selection
    if st.session_state.selected_repo and st.session_state.prs:
        pr = st.selectbox("Select Pull Request", st.session_state.prs, key="pr_select")

        REPO_NAME = st.session_state.selected_repo
        PULL_REQUEST_NUMBER = pr # pr is (title, number)
        pat_token = st.session_state.token

        # # Display selected values in the main screen
        # if REPO_NAME and PULL_REQUEST_NUMBER and pat_token:
        #     st.write("### Selected Repository")
        #     st.write(REPO_NAME)
        #     st.write("### Selected Pull Request")
        #     st.write(f"Title: {PULL_REQUEST_NUMBER}")
        #     st.write(f"Number: {PULL_REQUEST_NUMBER[1]}")
        #     st.write("### PAT Token")
        #     st.write(pat_token)


    st.header("Prometheus config", help="Enter the URL of your Prometheus instance. This is autofilled with the default value for the prometheus in East US region. If you're using a different region and subscription, Ensure the client ID has all the required permissions to access the Prometheus instance.")
    prometheus_url = st.text_input("Prometheus URL", value="https://prometheusmdmeastus-stage-060d.eastus.prometheus.monitor.azure.com", key="prometheus_url")
    subscription_id = st.text_input("Subscription ID", value= "19998cf7-a1b7-4c69-8daf-1f026e397d66", key="subscription_id")
    resource_group = st.text_input("Resource Group", value="anf.dc.mgmt.eastus-stage.rg", key="resource_group")
    client_id = st.text_input("Client ID", value = "53b97f90-8c73-44f5-9bdc-5a668226e87b",key="client_id")


    # Main window: Show chat if PR is selected
    if REPO_NAME and PULL_REQUEST_NUMBER and pat_token:
        st.session_state.show_chat = True
        st.session_state.chat_repo = REPO_NAME
        st.session_state.chat_pr = PULL_REQUEST_NUMBER
        st.session_state.chat_token = pat_token
    else:
        st.session_state.show_chat = False

# Warm up model only once per session
if 'model_warmed_up' not in st.session_state:
    # os.system('ollama run llama3.3:latest what is water short answer')
    os.system(f'ollama run {selected_model} what is water short answer')
    st.session_state.model_warmed_up = True

if 'model_to_use' not in st.session_state:
    st.session_state.model_to_use = ChatOllama(model=selected_model, temperature=temperature)

model_to_use = st.session_state.model_to_use


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
        "You are a supervisor managing the following agents:\n"
        "- a observability agent. Assign observability-related tasks to this agent\n"
        "- a security agent. Assign security-related tasks to this agent\n"
        "- a database agent. Assign database-related tasks to this agent\n"
        "- a quality agent. Assign quality-related tasks to this agent\n"
        "Assign work to one agent at a time, do not call agents in parallel.\n"
        "Do not do any work yourself.\n"
        "If there are questions not related to any of the agents you manage, respond with an answer and also a warning to interact with only PRR related questions"
    ),
    add_handoff_back_messages=True,
    output_mode="last_message",
).compile()


# if st.session_state.get("show_chat"):
#     st.subheader(f"Chat about PR: {st.session_state.chat_pr[0]} (#{st.session_state.chat_pr[1]}) in {st.session_state.chat_repo}")

#     if 'chat_history' not in st.session_state:
#         # Initialize with a greeting from the agent
#         st.session_state.chat_history = [
#             {"role": "agent", "content": "Hello! I'm your PRR agent. How can I assist you with this pull request?"}
#         ]

#     # Chat bubbles with colors
#     for msg in st.session_state.chat_history:
#         if msg['role'] == "user":
#             st.markdown(
#                 f"""
#                 <div style='background-color:#d4edda; color:#155724; border-radius:10px; padding:10px; margin:5px 0 5px 40px; text-align:right;'>
#                     <b>You:</b> {msg['content']}
#                 </div>
#                 """,
#                 unsafe_allow_html=True,
#             )
#         else:
#             st.markdown(
#                 f"""
#                 <div style='background-color:#cce5ff; color:#004085; border-radius:10px; padding:10px; margin:5px 40px 5px 0; text-align:left;'>
#                     <b>Agent:</b> {msg['content']}
#                 </div>
#                 """,
#                 unsafe_allow_html=True,
#             )

#     with st.form(key="chat_form", clear_on_submit=True):
#         user_input = st.text_input("Type your message...", key="chat_input")
#         send_clicked = st.form_submit_button("Send")
#         if (send_clicked or (user_input and user_input != st.session_state.get("last_user_input"))) and user_input:
#             st.session_state["last_user_input"] = user_input
#             st.session_state.chat_history.append({"role": "user", "content": user_input})

#             # Prepare context for the supervisor agent
#             pr_title, pr_number = st.session_state.chat_pr
#             repo_name = st.session_state.chat_repo
#             pat_token = st.session_state.chat_token

#             # Compose context for the supervisor agent
#             context = {
#                 "repo_name": repo_name,
#                 "pr_number": pr_number[1] if isinstance(pr_number, tuple) else pr_number,
#                 "github_token": pat_token,
#                 "user_message": user_input,
#                 "prometheus_url": st.session_state.get("prometheus_url"),
#                 "subscription_id": st.session_state.get("subscription_id"),
#                 "resource_group": st.session_state.get("resource_group"),
#                 "client_id": st.session_state.get("client_id"),
#             }

#             # # Accumulate all outputs from the stream
#             # from io import StringIO
#             # import sys
#             # buffer = StringIO()
#             # sys_stdout = sys.stdout
#             # sys.stdout = buffer
#             # for chunk in supervisor.stream(
#             #     {"messages": [{"role": "user", "content": f"{user_input} with context of {context}"}]}
#             # ):
#             #     pretty_print_messages(chunk)
#             # sys.stdout = sys_stdout
#             # output = buffer.getvalue().strip()
#             # st.session_state.chat_history.append({"role": "agent", "content": output})
#             # st.rerun()

#             # Accumulate all pretty-printed outputs from the stream into a buffer
#             from io import StringIO
#             buffer = StringIO()
#             # Call supervisor.stream only once and pretty print each chunk into the buffer
#             # for full tool call output
#             for chunk in supervisor.stream(
#                 {"messages": [{"role": "user", "content": f"{user_input} with context of {context}"}]}
#             ):
#                 # Capture the output of pretty_print_messages by redirecting stdout
#                 import sys
#                 sys_stdout = sys.stdout
#                 sys.stdout = buffer
#                 pretty_print_messages(chunk, last_message=summarized_response) # for conscised output last_message=True
#             output = buffer.getvalue().strip()
#             st.session_state.chat_history.append({"role": "agent", "content": output})
#             st.rerun()


if st.session_state.get("show_chat"):
    st.subheader(f"Chat about PR: {st.session_state.chat_pr[0]} (#{st.session_state.chat_pr[1]}) in {st.session_state.chat_repo}")

    if 'chat_history' not in st.session_state:
        # Initialize with a greeting from the agent
        st.session_state.chat_history = [
            {"role": "agent", "content": "Hello! I'm your PRR agent. How can I assist you with this pull request?"}
        ]

    # Chat bubbles with feedback for agent responses
    for idx, msg in enumerate(st.session_state.chat_history):
        if msg['role'] == "user":
            st.markdown(
                f"""
                <div style='background-color:#d4edda; color:#155724; border-radius:10px; padding:10px; margin:5px 0 5px 40px; text-align:right;'>
                    <b>You:</b> {msg['content']}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style='background-color:#cce5ff; color:#004085; border-radius:10px; padding:10px; margin:5px 40px 5px 0; text-align:left;'>
                    <b>Agent:</b> {msg['content']}
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Add feedback widget for agent responses (except the initial greeting)
            if idx > 0:
                feedback_key = f"feedback_{idx}"
                feedback = streamlit_feedback(
                    # "How helpful was this response?",
                    key=feedback_key,
                    # optional=True,
                    feedback_type="thumbs",
                    optional_text_label = "[Optional] Please provide an explanation",
                    align="flex-start"
                )

                if feedback is not None:
                    if 'feedback_log' not in st.session_state:
                        st.session_state.feedback_log = {}
                    st.session_state.feedback_log[feedback_key] = feedback

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Type your message...", key="chat_input")
        send_clicked = st.form_submit_button("Send")
        if (send_clicked or (user_input and user_input != st.session_state.get("last_user_input"))) and user_input:
            st.session_state["last_user_input"] = user_input
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            # Prepare context for the supervisor agent
            pr_title, pr_number = st.session_state.chat_pr
            repo_name = st.session_state.chat_repo
            pat_token = st.session_state.chat_token

            # Compose context for the supervisor agent
            context = {
                "repo_name": repo_name,
                "pr_number": pr_number[1] if isinstance(pr_number, tuple) else pr_number,
                "github_token": pat_token,
                "user_message": user_input,
                "prometheus_url": st.session_state.get("prometheus_url"),
                "subscription_id": st.session_state.get("subscription_id"),
                "resource_group": st.session_state.get("resource_group"),
                "client_id": st.session_state.get("client_id"),
            }

            buffer = StringIO()
            # Only provide context if the user_input is related to PRR (pull request review)
            prr_keywords = [
                "pull request", "PR", "code review", "observability", "security", "database", "quality",
                "diff", "alert", "metric", "log", "runbook", "TSG", "dependency", "exception", "encryption",
                "secret", "base image", "performance", "scalability", "error handling", "best practice"
            ]
            is_prr_related = any(kw.lower() in user_input.lower() for kw in prr_keywords)
            if is_prr_related:
                supervisor_input = {"messages": [{"role": "user", "content": f"{user_input} with context of {context}"}]}
            else:
                supervisor_input = {"messages": [{"role": "user", "content": user_input}]}

            for chunk in supervisor.stream(supervisor_input):
                sys_stdout = sys.stdout
                sys.stdout = buffer
                pretty_print_messages(chunk, last_message=summarized_response)
                sys.stdout = sys_stdout
            output = buffer.getvalue().strip()
            st.session_state.chat_history.append({"role": "agent", "content": output})

            # --- Save all conversations in one JSON file per session ---
            # Prepare the conversation log in session state
            if 'conversation_log' not in st.session_state:
                st.session_state.conversation_log = {
                    "user_name": st.session_state.get("user_name"),
                    "email": st.session_state.get("email"),
                    "start_timestamp": datetime.now().isoformat(),
                    "model_config": {
                        "model": selected_model,
                        "temperature": temperature,
                        "summarized_response": summarized_response,
                    },
                    "github_config": {
                        "repo_name": repo_name,
                        "pr_number": pr_number[1] if isinstance(pr_number, tuple) else pr_number,
                        "github_token": pat_token,
                    },
                    "conversations": []
                }

            # # Get feedback for the previous agent response (not the one just appended)
            # feedback_key = f"feedback_{len(st.session_state.chat_history)-1}"
            # feedback_value = None
            # if 'feedback_log' in st.session_state:
            #     feedback_value = st.session_state.feedback_log.get(feedback_key)

            # # Append the current exchange, including feedback for the previous agent response
            # st.session_state.conversation_log["conversations"].append({
            #     "timestamp": datetime.now().isoformat(),
            #     "user_input": user_input,
            #     "agent_response": output,
            #     "feedback": feedback_value
            # })

            # # Find the feedback for this agent response
            # agent_idx = len(st.session_state.conversation_log["conversations"])
            # feedback_key = f"feedback_{find_agent_chat_history_idx(agent_idx)}"
            # feedback_value = None
            # if 'feedback_log' in st.session_state:
            #     feedback_value = st.session_state.feedback_log.get(feedback_key)

            # st.session_state.conversation_log["conversations"].append({
            #     "timestamp": datetime.now().isoformat(),
            #     "user_input": user_input,
            #     "agent_response": output,
            #     "feedback": feedback_value
            # })
            # When appending a new conversation (after agent response)
            # Find the chat_history index for this agent response (skip greeting)
            agent_idx = len(st.session_state.conversation_log["conversations"])
            chat_history_idx = find_agent_chat_history_idx(agent_idx + 1)  # +1 to skip greeting
            feedback_key = f"feedback_{chat_history_idx}"
            feedback_value = None
            if 'feedback_log' in st.session_state:
                feedback_value = st.session_state.feedback_log.get(feedback_key)

            # Append the current exchange (no feedback yet)
            st.session_state.conversation_log["conversations"].append({
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input,
                "agent_response": output,
                "feedback": None  # Will be updated below
            })

            # --- Update feedback for all agent responses before saving ---
            for agent_idx, conv in enumerate(st.session_state.conversation_log["conversations"]):
                chat_history_idx = find_agent_chat_history_idx(agent_idx + 1)  # +1 to skip greeting
                feedback_key = f"feedback_{chat_history_idx}"
                feedback_value = None
                if 'feedback_log' in st.session_state:
                    feedback_value = st.session_state.feedback_log.get(feedback_key)
                conv["feedback"] = feedback_value

            # Save the conversation log to a new file for every session (unique filename per session)
            try:
                session_id = st.session_state.conversation_log.get("start_timestamp", datetime.now().isoformat()).replace(":", "-")
                logs_dir = "/home/azureuser/prrenv/prr/StreamlitApp/logs/"
                os.makedirs(logs_dir, exist_ok=True)
                filename = os.path.join(
                    logs_dir,
                    f"prr_conversation_{st.session_state.conversation_log['github_config']['repo_name'].replace('/','_')}_{st.session_state.conversation_log['github_config']['pr_number']}_{session_id}.json"
                )
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.conversation_log, f, indent=2)
            except Exception as e:
                st.warning(f"Could not save conversation: {e}")

            # Ensure conversation is saved on app shutdown
            def save_on_shutdown():
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(st.session_state.conversation_log, f, indent=2)
                except Exception:
                    pass

            if not st.session_state.get("atexit_registered"):
                atexit.register(save_on_shutdown)
                st.session_state.atexit_registered = True
            # --- End save ---

            st.rerun()
