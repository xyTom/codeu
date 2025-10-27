import os

from langchain_openai import ChatOpenAI

def init_chat_model():
    return ChatOpenAI(
        model="ep-20251015144800-d5pzt",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=os.getenv("ARK_API_KEY"), # 替换为你自己的 Key
        temperature=0.7,
        max_tokens=32768,
        # extra_body={
        #     "thinking": {
        #         "type": "disabled"  # 如果需要推理，这里可以设置为 "auto"
        #     }
        # }
    )