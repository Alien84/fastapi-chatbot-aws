from fastapi.testclient import TestClient
from app.main_using_secret_manager import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "online", "message": "Welcome to the Chatbot API"}

def test_chat_endpoint():
    response = client.post("/chat", json={"content": "Hello"})
    assert response.status_code == 200
    assert "response" in response.json()
    assert response.json()["response"] == "You said: Hello"