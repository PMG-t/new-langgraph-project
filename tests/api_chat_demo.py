import asyncio
from langgraph_sdk import get_client



client = get_client(url="http://localhost:2024")



async def create_thread():
    thread = await client.threads.create()
    print(f"Creato nuovo thread con ID: {thread['thread_id']}")
    return thread['thread_id']


async def ask_bot(thread_id: str, message: str):
    
    async for chunk in client.runs.stream(
        thread_id,  # No thread ID per ora, oppure uno esistente
        "agent",
        input={"messages": [{"role": "human", "content": message}]},
        stream_mode="updates",
    ):
        if chunk.event == "updates":
            if "chatbot" in chunk.data and "messages" in chunk.data['chatbot']:
                for update in chunk.data['chatbot']['messages']:
                    print(f'BOT: {update["content"]}', end="", flush=True)
    print()  # Vai a capo dopo la risposta completa
    

async def chat_loop():
    
    thread_id = await create_thread() 
    
    print("Chat con il tuo bot LangChain. Scrivi 'exit' per uscire.")
    while True:
        user_input = input("Tu: ")
        if user_input.lower() in {"exit", "quit"}:
            break
        await ask_bot(thread_id, user_input)

# Avvia l'event loop
if __name__ == "__main__":
    asyncio.run(chat_loop())

