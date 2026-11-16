import streamlit as st
from langchain_core.language_models._compat_bridge import message_to_events
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
import sqlite3
import uuid

load_dotenv()

def generate_thread_id():
    thread_id = uuid.uuid4()
    return thread_id

def reset_chat():
    thread_id = generate_thread_id()
    st.session_state["thread_id"] = thread_id
    add_thread_id(st.session_state["thread_id"])
    st.session_state["message_history"]=[]

def retrive_all_threads(checkpoint):
    all_thread=set()
    for checkpoint in checkpoint.list(None):
        all_thread.add(checkpoint.config["configurable"]["thread_id"])
    return(list(all_thread))

def add_thread_id(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)
    

def load_conversation(thread_id):
    return chatbot.get_state(config={"configurable":{"thread_id":thread_id}}).values['message']

llm = ChatOpenAI(model ="gpt-4o")


class chatstate(TypedDict):
    message : Annotated[list[BaseMessage], add_messages]

def chat_model(state : chatstate):
    response = llm.invoke(state["message"])
    return {"message": [response]}

@st.cache_resource
def get_checkpointer():
    conn = sqlite3.connect("Chatbot.db", check_same_thread=False)
    return SqliteSaver(conn=conn)

checkpoint = get_checkpointer()

graph = StateGraph(chatstate)

graph.add_node("chat_model", chat_model)

graph.add_edge(START , "chat_model")
graph.add_edge("chat_model", END)

chatbot = graph.compile(checkpointer=checkpoint)

#***************************************** Session State ******************************************
if "message_history" not in st.session_state:
    st.session_state["message_history"]=[]

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = retrive_all_threads(checkpoint)

add_thread_id(st.session_state["thread_id"])

#***************************************** UI sidebar ********************************************
st.sidebar.title("Langgraph Chatbot")

if st.sidebar.button("New Chat"):
    reset_chat()

st.sidebar.header("My Conversation")


for thread_id in st.session_state["chat_threads"][::-1]:
        if st.sidebar.button(str(thread_id)):
            st.session_state["thread_id"] = thread_id
            try:
                messages = load_conversation(thread_id)

                temp_messages = []
                for message in messages:
                    if isinstance(message, HumanMessage):
                        role = "user"
                    else :
                        role = "assistant"
                    temp_messages.append({"role":role, "content": message.content})
                st.session_state["message_history"] = temp_messages
            except:
                pass



#***************************************** Message memory *****************************************

CONFIG = {"configurable":{"thread_id":st.session_state["thread_id"]}}

for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.text(message["content"])
    
user_input = st.chat_input("Type here")

if user_input:

    st.session_state["message_history"].append({"role":"user", "content": user_input})
    with st.chat_message("user"):
        st.text(user_input)

    with st.chat_message("assistant"):
        ai_message = st.write_stream(
            message_chunk for message_chunk, metadata in chatbot.stream(
                {"message": [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode="messages"
            )
        )
    st.session_state["message_history"].append({"role":"assistant", "content": ai_message})
