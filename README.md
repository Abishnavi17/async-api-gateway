# async-api-gateway
# Async API Gateway

A lightweight and simple API Gateway built in Python. It acts as a single entry point to manage, secure, and log network traffic requests for an application.

## 🌟 Key Features
* **Handles Multiple Requests:** Uses FastAPI's asynchronous code (`async/await`) to handle many incoming client connections at the same time without slowing down.
* **Prevents System Overload (Rate Limiting):** Automatically blocks any user or IP address that sends too many requests too quickly (caps at 20 requests per 60 seconds).
* **Security Check:** Requires an API key (`x-api-key`) in the request header before allowing access to important endpoints.
* **Smart Background Logging:** Saves traffic history and server metrics into an SQLite database. It runs database writes on separate threads (`asyncio.to_thread`) so the main application never freezes while saving data.

## 🛠️ Requirements & Tech Stack
You only need Python installed on your computer along with two lightweight libraries:
* **FastAPI** (The core web framework)
* **Uvicorn** (The server engine used to run the code)

## 📁 File Structure
* `api_gateway.py` — The core Python application script containing the gateway logic.
* `requirements.txt` — File containing the text: `fastapi` and `uvicorn`.

## 🚀 How to Run It Locally

1. Clone this repository to your computer:
```bash
git clone [https://github.com/Abishnavi17/async-api-gateway.git](https://github.com/Abishnavi17/async-api-gateway.git)
cd async-api-gateway
