import websocket
import threading
import time
import json

def on_message(ws, message):
    print("Received from server:", message)

def on_error(ws, error):
    print("Error:", error)

def on_close(ws, close_status_code, close_reason):
    print("WebSocket closed")

def on_open(ws):
    print("WebSocket connection opened")
    # Send a message to the server
    message = json.dumps({'type': 'greeting', 'message': 'Hello from Client!'})
    ws.send(message)

def websocket_client():
    ws = websocket.WebSocketApp("ws://localhost:8000/ws/play/room1/",
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    wst = threading.Thread(target=ws.run_forever)
    wst.start()
    time.sleep(5)  # Keep the connection for 5 seconds
    ws.close()
    wst.join()

if __name__ == "__main__":
    websocket_client()
