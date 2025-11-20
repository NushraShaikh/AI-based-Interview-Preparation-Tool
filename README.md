# ⭐ AI Interview Coach

A lightweight Flask-based web app that helps users practice interviews with **instant feedback, improvements, and scoring**.
Works fully **offline**, with optional support for **Ollama** to generate AI-based questions.

## 🚀 Features

 **Choose role, style, and number of questions**
 **AI-powered (optional) or offline question generator**
 **Instant per-answer feedback**
 **Improvement tips + Score (1–5)**
 **Average rating at the end**
 **Fully offline — no cloud API needed**
 Built using **Flask + Bootstrap**

## 🛠️ Tech Stack

* Python
* Flask
* Bootstrap 5
* Optional: Ollama (local LLM)

## 📦 Installation & Setup

### 1️⃣ Clone the repository

```bash
git clone <https://github.com/NushraShaikh/AI-based-Interview-Preparation-Tool>
cd <repo-folder>
```
### 2️⃣ Create a virtual environment (recommended)

```bash
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate  # Mac/Linux
```
### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```
### 4️⃣ Run the app

```bash
python quick_interview.py
```
### 5️⃣ Open in browser

```
http://127.0.0.1:5000
```

## 🤖 Optional: Enable Ollama Question Generation

1. Install & run Ollama
2. Download any model (e.g., phi3-mini)
3. In your code, set:

```python
USE_OLLAMA_FOR_QUESTIONS = True
```

If set to `False`, the tool uses the offline question generator.

## 🧠 How It Works (Short Explanation)

1. User selects role, interview style, and number of questions.
2. The app asks one question at a time.
3. User submits answer → app evaluates using a heuristic model.
4. Feedback includes:

   * Strengths
   * Improvements
   * Score
5. After all questions → summary page with average score.

## 📌 Future Enhancements (Optional)

* Persistent history (SQLite)
* User accounts
* Voice mode (mic input + TTS)
* Better LLM question generation
* Custom rubrics for each domain

CONTACT
Name: Nusra Shaikh
Email: nushrashaikh9@gmail.com


