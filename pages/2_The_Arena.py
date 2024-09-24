import sys
import ollama
import streamlit as st
import asyncio
import time
import base64
from openai import AsyncOpenAI
from streamlit_extras.stylable_container import stylable_container
from streamlit_extras.bottom_container import bottom
import random
from utils import style_page, clear_everything, meta_formatting, create_logger
import uuid

from functools import partial

voting_logger = create_logger("voting", "logs/voting.log")
requests_logger = create_logger("requests", "logs/requests.log")

title = "The Arena"
st.set_page_config(page_title=title, layout="wide")
style_page()
st.title(title)

if not "models" in st.session_state:
    st.session_state.models = []

if not "models" in st.session_state or len(st.session_state.models) < 2:
    if len(st.session_state.models) == 0:
        st.write("You haven't selected any models, so the arena won't be much use!")
    if len(st.session_state.models) == 1:
        st.write("You have only selected 1 mode. Go back and select one more!")
    if st.button("Select models"):
        st.switch_page("pages/1_Select_Models.py")
    st.stop()


if not "messages1" in st.session_state:
    st.session_state.messages1 = []

if not "messages2" in st.session_state:
    st.session_state.messages2 = []

client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ignore-me")


if not "selected_models" in st.session_state or len(st.session_state.selected_models) == 0:
    st.session_state.selected_models = random.sample(st.session_state.models, 2)

model_1, model_2 = st.session_state.selected_models

col1, col2 = st.columns(2)

meta_1 = col1.empty()
meta_2 = col2.empty()

meta_1.write(f"### :blue[Model 1: {model_1}]")
meta_2.write(f"### :red[Model 2: {model_2}]")

body_1 = col1.empty()
body_2 = col2.empty()

with bottom():
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        temperature = st.slider('Temperature', min_value=0.0, max_value=1.0, value=0.7, step=0.01)

    with col2:
        max_tokens = st.slider('Max Tokens', min_value=1, max_value=4000, value=1000)

    with col3:
        top_p = st.slider('Top P', min_value=0.0, max_value=1.0, value=1.0, step=0.01)

    with col4:
        frequency_penalty = st.slider('Frequency Penalty', min_value=0.0, max_value=2.0, value=0.0, step=0.01)

    with col5:
        presence_penalty = st.slider('Presence Penalty', min_value=0.0, max_value=2.0, value=0.0, step=0.01)

    prompt = st.chat_input("Message")
    new_found = st.empty()
    with new_found.container():
        if len(st.session_state.messages1) > 0 or len(st.session_state.messages2) > 0:
            with stylable_container(
                key="next_round_button",
                css_styles="""
                    button {
                        background-color: green;
                        color: white;
                        border-radius: 10px;
                        width: 100%
                    }
                    """,
            ):
                new_round = st.button("New Round", key="new_round", on_click=clear_everything)


# Render existing state
if "vote" in st.session_state:
    model_1_display= model_1.replace(":", "\\:")
    model_2_display= model_2.replace(":", "\\:")
    meta_1.write(partial(meta_formatting, "blue", "Model 1")(model_1_display))
    meta_2.write(partial(meta_formatting, "red", "Model 2")(model_2_display))

if len(st.session_state.messages1) > 0 or len(st.session_state.messages2) > 0:
    with body_1.container():
        for message in st.session_state.messages1:
            chat_entry = st.chat_message(name=message['role'])
            chat_entry.write(message['content'])

    with body_2.container():
        for message in st.session_state.messages2:
            chat_entry = st.chat_message(name=message['role'])
            chat_entry.write(message['content'])

async def run_prompt(placeholder, model, message_history):
    with placeholder.container():
        for message in message_history:
            chat_entry = st.chat_message(name=message['role'])
            chat_entry.write(message['content'])
        assistant = st.chat_message(name="assistant")

        with open("images/loading-gif.gif", "rb") as file:
            contents = file.read()
            data_url = base64.b64encode(contents).decode("utf-8")

        assistant.html(f"<img src='data:image/gif;base64,{data_url}' class='spinner' width='25' />")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        *message_history
    ]

    request_id = str(uuid.uuid4())
    requests_logger.info("Request starts", id=request_id, model=model, prompt=message_history[-1]["content"])
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True
    )
    streamed_text = ""
    async for chunk in stream:
        chunk_content = chunk.choices[0].delta.content
        if chunk_content is not None:
            streamed_text = streamed_text + chunk_content
            with placeholder.container():
                for message in message_history:
                    chat_entry = st.chat_message(name=message['role'])
                    chat_entry.write(message['content'])
                assistant = st.chat_message(name="assistant")
                assistant.write(streamed_text)
    requests_logger.info("Request finished", id=request_id, model=model, response=streamed_text)

    message_history.append({"role": "assistant", "content": streamed_text})

def vote():
    with new_found.container():
        with stylable_container(
            key="next_round_button",
            css_styles="""
                button {
                    background-color: green;
                    color: white;
                    border-radius: 10px;
                    width: 100%
                }
                """,
        ):
            new_round = st.button("New Round", key="new_round_later", on_click=clear_everything)

async def main():
    await asyncio.gather(
        run_prompt(body_1,  model=model_1, message_history=st.session_state.messages1),
        run_prompt(body_2,  model=model_2, message_history=st.session_state.messages2)
    )
    if "vote" not in st.session_state:
        vote()

if prompt:
    if prompt == "":
        st.warning("Please enter a prompt")
    else:
        st.session_state.messages1.append({"role": "user", "content": prompt})
        st.session_state.messages2.append({"role": "user", "content": prompt})
        asyncio.run(main())
