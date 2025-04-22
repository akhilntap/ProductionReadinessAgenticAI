import streamlit as st
from langragphworkflow import analyze_observability

# Streamlit app
st.title("PRR Chatbot")

# Sidebar for model selection
st.sidebar.header("Model Selection")
model = st.sidebar.selectbox(
    "Select a model:",
    ["gpt-4o-mini", "o3-mini", "o1", "o1-mini", "gpt-4o", "gpt-35-turbo", "gpt-35-turbo-16k"]
)

# Chat interface
st.header("Make sure you're connected to vpn")
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history with visual differentiation
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(
            f'''
            <div style="
                display: flex; 
                justify-content: flex-end; 
                margin-bottom: 10px;">
                <div style="
                    background-color: #d1e7dd; 
                    color: #0f5132; 
                    padding: 10px; 
                    border-radius: 15px 15px 0 15px; 
                    max-width: 70%; 
                    word-wrap: break-word;">
                    <strong>You:</strong> {message["content"]}
                </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'''
            <div style="
                display: flex; 
                justify-content: flex-start; 
                margin-bottom: 10px;">
                <div style="
                    background-color: #f8d7da; 
                    color: #842029; 
                    padding: 10px; 
                    border-radius: 15px 15px 15px 0; 
                    max-width: 70%; 
                    word-wrap: break-word;">
                    <strong>Bot:</strong> {message["content"]}
                </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

# User input
def handle_input():
    if st.session_state.user_input:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": st.session_state.user_input})

        # Call the analyze_observability function
        try:
            bot_response = analyze_observability(model, st.session_state.user_input)
            st.session_state.messages.append({"role": "bot", "content": bot_response})
        except Exception as e:
            st.session_state.messages.append({"role": "bot", "content": f"Error: {str(e)}"})

        # Clear the input field
        st.session_state.user_input = ""

user_input = st.text_input("Type your message:", key="user_input", on_change=handle_input)