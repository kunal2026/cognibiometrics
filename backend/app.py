from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import threading

from agent import CognitiveAgent, global_state

app = FastAPI(title="Cognitive-Biometric Web Prototype")

agent = CognitiveAgent(global_state)
agent_thread_started = False

@app.on_event("startup")
def startup_event():
    global agent_thread_started
    if not agent_thread_started:
        agent.start()
        agent_thread_started = True

@app.get("/api/status")
def get_status():
    return global_state.get_snapshot()

# Serve SPA
app.mount("/static", StaticFiles(directory="../frontend", html=False), name="static")

@app.get("/")
def index():
    return FileResponse("../frontend/index.html")
