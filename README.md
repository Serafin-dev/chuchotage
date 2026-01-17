# Chuchotage 🤫

Chuchotage (French for "whispering") is a real-time voice translation application built with Django Channels, Deepgram, and Groq. It allows users to join rooms and have their speech translated and synthesized into another language in real-time.

## 🚀 Features

- **Real-time Speech-to-Text (STT)** using Deepgram.
- **Fast Translation** using Groq (Llama 3 models).
- **Text-to-Speech (TTS)** using Deepgram Aura.
- **WebSockets** for low-latency communication (Django Channels).
- **Dockerized Redis** for channel layers.

## 🛠 Prerequisites

- Python 3.10+
- Docker & Docker Compose
- API Keys for:
  - [Deepgram](https://deepgram.com/)
  - [Groq](https://groq.com/)

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone <repository_url>
   cd chuchotage
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API Keys**
   Open `translator/constants.py` and add your API keys:
   ```python
   # translator/constants.py
   DEEPGRAM_API_KEY = 'your_deepgram_key'
   GROQ_API_KEY = 'your_groq_key'
   ```
   > **Note:** It is recommended to use environment variables for security, but direct assignment works for development.

## 🏃‍♂️ Running the Application

1. **Start Redis**
   The application requires Redis for Django Channels. Start it using Docker Compose:
   ```bash
   docker-compose up -d
   ```

2. **Apply Migrations**
   Initialize the database:
   ```bash
   python manage.py migrate
   ```

3. **Run the Server**
   Start the ASGI development server:
   ```bash
   python manage.py runserver
   ```
   The application will be available at `http://127.0.0.1:8000`.

## 🧹 Maintenance

To clean up compiled Python files and cache:
```bash
make clean
```

## 🏗 Project Structure

- **backend/**: Main Django project settings and ASGI config.
- **translator/**: Core application logic.
  - `consumers.py`: Handles WebSocket connections and real-time processing chain (STT -> Translation -> TTS).
  - `translation_service.py`: Service for handling translations via Groq.
  - `templates/`: Contains the frontend `index.html`.
- **docker-compose.yml**: Configuration for the Redis service.
