import os
import streamlit as st
from pymongo import MongoClient
from bson import ObjectId
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBg7MHeMJvxfrWY2it8WtRvAP9OytV82S8")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:yourStrongPassword@34.16.116.26:27017/test?authSource=admin")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# Read prompt template with explicit UTF-8 encoding
with open("prompt.txt", "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client.test  # Replace "test" with your database name

# Streamlit UI
st.set_page_config(page_title="JustDeliveries Support", page_icon="🚚")
st.title("🚚 JustDeliveries Support Chatbot")

# Configuration in sidebar
with st.sidebar:
    st.header("Settings")
    driver_id = st.text_input("Enter Driver_ID (ObjectId):", value="677cb2c8e142e00787bb4a59") # Default for convenience
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=message.get("avatar")):
        st.markdown(message["content"])

# Chat input
if user_query := st.chat_input("How can I help you today?"):
    if not driver_id:
        st.error("Please enter a Driver_ID in the sidebar first!")
    else:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_query, "avatar": "👤"})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_query)

        # Generate Assistant response
        with st.chat_message("assistant", avatar="🚚"):
            response_placeholder = st.empty()
            response_placeholder.markdown("🔄 *Thinking...*")
            
            try:
                # Step 1: Generate MongoDB query
                prompt = PROMPT_TEMPLATE.replace("{question}", user_query).replace("{driver_id}", driver_id)
                response = model.generate_content(prompt)
                
                # Robust extraction: find the first '{' and last '}'
                raw_text = response.text.strip()
                start_idx = raw_text.find('{')
                end_idx = raw_text.rfind('}')
                
                if start_idx == -1 or end_idx == -1:
                    # Fallback if no JSON object is found at all
                    clean_response = "{}" 
                else:
                    clean_response = raw_text[start_idx:end_idx+1]
                
                from bson import json_util
                query_data = json_util.loads(clean_response)
                collection_name = query_data.get("collection")
                mongo_pipeline = query_data.get("pipeline", [])

                if not collection_name or collection_name == "none":
                    # Step 2 (Fallback): Generate a friendly general response
                    general_prompt = f"""
                    You are a friendly JustDeliveries driver support assistant.
                    The driver said: "{user_query}"
                    
                    This query is not related to a specific database search. 
                    Please provide a friendly, helpful, and natural follow-up response.
                    If it's a greeting, greet them back warmly! 
                    If it's a general question, try to answer it if possible, or offer to help with driver-related info.
                    Use appropriate emojis. 🚚✨
                    """
                    gen_response = model.generate_content(general_prompt)
                    assistant_response = gen_response.text
                else:
                    # Execute MongoDB query
                    result = list(db[collection_name].aggregate(mongo_pipeline))

                    # Step 2: Generate natural language response from DB result
                    summary_prompt = f"""
                    You are a helpful JustDeliveries driver support assistant.
                    The driver asked: "{user_query}"
                    The database returned the following data from the '{collection_name}' collection:
                    {result}
                    
                    Please provide a natural, friendly, and concise response to the driver in English.
                    Use appropriate emojis in your response. 🚚
                    If the result is empty, politely explain that you couldn't find any information for their request.
                    Do not mention technical details like 'collection names' or 'pipelines'.
                    """
                    
                    summary_response = model.generate_content(summary_prompt)
                    assistant_response = summary_response.text

                # Display finalized response
                response_placeholder.markdown(assistant_response)
                st.session_state.messages.append({"role": "assistant", "content": assistant_response, "avatar": "🚚"})


            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                response_placeholder.error(error_msg)
                import traceback
                st.code(traceback.format_exc())
