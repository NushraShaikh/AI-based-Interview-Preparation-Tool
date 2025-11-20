
from flask import Flask, request, session, redirect, url_for, render_template_string
from datetime import datetime
import requests

app = Flask(__name__)
app.config["SECRET_KEY"] = "supersecret_demo_key"  # change if you want

# ---------- CONFIG ----------
USE_OLLAMA_FOR_QUESTIONS = True  #Can be set to 'False'
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "phi3:mini"
REQUEST_TIMEOUT = 30
OLLAMA_OPTIONS = {"temperature": 0.3, "top_p": 0.9, "num_predict": 48, "num_ctx": 512}
KEEP_ALIVE = "15m"
# ----------------------------

# ----------LLM question generator
def ollama_one_question(role, style):
    url = OLLAMA_HOST.rstrip("/") + "/api/chat"
    system = (
        "You are an expert interviewer. Generate EXACTLY ONE interview question. "
        "Keep it short (<= 15 words). No preface, no extra text. Output only the question."
    )
    user = f"Style: {style}\nRole: {role}\nGive one concise question."
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "options": OLLAMA_OPTIONS,
        "keep_alive": KEEP_ALIVE,
    }
    try:
        r = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        txt = (data.get("message", {}) or {}).get("content", "") or data.get("content", "")
        q = (txt or "").strip().strip('"').strip("'")
        if not q:
            return None
        # only keep first line/sentence
        q = q.splitlines()[0]
        if len(q) > 120:
            q = q[:117] + "..."
        return q
    except Exception:
        return None
# ----------------------------------------------------------------------

# ----------------- offline helpers  -----------------
def offline_first_question(role, style):
    s = (style or "").lower()
    if s.startswith("tech"):
        return f"Explain a core concept you recently used as a {role}."
    if s.startswith("situ"):
        return f"Describe a tough situation you faced as a {role} and what you did."
    return f"Tell me about a time you showed a key strength as a {role}."

def offline_eval_and_next(role, style, question, answer):
    """Heuristic evaluator: harsher on weak answers, rewards structure + specifics."""
    ans = (answer or "").strip()
    low = ans.lower()

    if not ans or low in {"na", "n/a"} or "i don't know" in low or "idk" in low:
        return {
            "feedback": ["No substantive answer provided."],
            "improvements": [
                "Attempt the question even if unsure; share your best reasoning.",
                "Give a short example or outline what you would try first."
            ],
            "score": 1,
            "next_question": f"What is one key strength you bring to a {role} role?"
        }

    feedback, improvements = [], []

    has_star = all(k in low for k in ["situation", "task", "action", "result"])
    has_numbers = any(ch.isdigit() for ch in ans)
    has_paras = "\n" in ans or len(ans.split(". ")) >= 2

    tech_words = {
        "data scientist": ["python", "pandas", "sklearn", "regression", "classification",
                           "feature", "pipeline", "cross-validation", "auc", "precision",
                           "recall", "f1", "xgboost", "tensorflow", "pytorch", "sql"],
        "software engineer": ["api", "http", "database", "cache", "thread", "latency",
                              "python", "java", "node", "ci/cd", "testing", "docker"],
        "teacher": ["lesson", "assessment", "rubric", "scaffold", "differentiation",
                    "classroom management", "outcomes", "curriculum"]
    }
    role_l = role.lower()
    role_terms = []
    for k, words in tech_words.items():
        if k in role_l:
            role_terms = words
            break
    has_role_terms = any(w in low for w in role_terms) if role_terms else False

    L = len(ans)
    if L < 20:
        base = 1
        improvements.append("Answer is extremely short—write 3–6 sentences minimum.")
    elif L < 80:
        base = 2
        improvements.append("Add more detail (what you did, why, and the result).")
    elif L < 200:
        base = 3
    elif L < 450:
        base = 4
    else:
        base = 5
        feedback.append("Good depth and coverage.")

    bonus = 0
    if has_star:
        bonus += 1; feedback.append("Uses STAR structure.")
    else:
        improvements.append("Try STAR: Situation, Task, Action, Result.")

    if has_numbers:
        bonus += 1; feedback.append("Includes metrics or concrete results.")
    else:
        improvements.append("Mention metrics (%, time saved, accuracy, ROI).")

    if has_role_terms:
        bonus += 1; feedback.append("Relevant domain terminology used.")
    else:
        improvements.append(f"Use {role} terminology where appropriate.")

    if not has_paras:
        improvements.append("Break the answer into clear sentences/paragraphs.")

    score = max(1, min(5, base + bonus - 1))

    s = (style or "").lower()
    if s.startswith("tech"):
        next_q = f"Walk me through debugging a tricky issue you solved as a {role}."
    elif s.startswith("situ"):
        next_q = f"Describe a time you handled conflicting priorities as a {role}."
    else:
        next_q = f"What is one key strength you bring to a {role} role?"

    def dedup(xs):
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x); out.append(x)
        return out[:4]

    return {
        "feedback": dedup(feedback) or ["Good effort."],
        "improvements": dedup(improvements) or ["Be concise and specific."],
        "score": score,
        "next_question": next_q
    }
# ----------------------------------------------------------------------

def init_state(role, style, n):
    session["state"] = {
        "role": role,
        "style": style,
        "n": n,
        "i": 0,
        "turns": [],
        "started": datetime.utcnow().isoformat(timespec="seconds")
    }

def state(): return session.get("state")
def finished(st): return st["i"] >= st["n"]

# ---------------------------- routes ----------------------------
@app.route("/", methods=["GET"])
def home():
    return render_template_string(INDEX_HTML)

def gen_first_question(role, style):
    if USE_OLLAMA_FOR_QUESTIONS:
        q = ollama_one_question(role, style)
        if q: return q
    return offline_first_question(role, style)

@app.route("/start", methods=["POST"])
def start():
    role = request.form.get("role","Data Scientist").strip()
    style = request.form.get("style","Behavioral").strip()
    try:
        n = max(1, min(20, int(request.form.get("num_questions","5"))))
    except:
        n = 5
    init_state(role, style, n)

    st = state()
    q = gen_first_question(st["role"], st["style"])
    st["turns"].append({"question": q, "answer": "", "feedback": [], "improvements": [], "score": None})
    session["state"] = st
    return redirect(url_for("ask"))

@app.route("/ask", methods=["GET"])
def ask():
    st = state()
    if not st: return redirect(url_for("home"))
    if finished(st): return redirect(url_for("summary"))

    i, total = st["i"], st["n"]
    turn = st["turns"][i]
    last = st["turns"][i-1] if i>0 else None
    progress = int((i/total)*100)
    return render_template_string(ASK_HTML, role=st["role"], style=st["style"],
                                  i=i, total=total, question=turn["question"],
                                  last=last, progress=progress)

@app.route("/answer", methods=["POST"])
def answer():
    st = state()
    if not st: return redirect(url_for("home"))
    if finished(st): return redirect(url_for("summary"))

    ans = (request.form.get("answer") or "").strip()
    if not ans: return redirect(url_for("ask"))

    i = st["i"]
    turn = st["turns"][i]
    turn["answer"] = ans

    parsed = offline_eval_and_next(st["role"], st["style"], turn["question"], ans)
    turn["feedback"] = parsed["feedback"]
    turn["improvements"] = parsed["improvements"]
    turn["score"] = parsed["score"]

    st["i"] += 1
    if not finished(st):
        st["turns"].append({
            "question": parsed["next_question"], "answer": "",
            "feedback": [], "improvements": [], "score": None
        })
    session["state"] = st

    return redirect(url_for("summary" if finished(st) else "ask"))

@app.route("/summary", methods=["GET"])
def summary():
    st = state()
    if not st: return redirect(url_for("home"))
    scores = [t["score"] for t in st["turns"] if isinstance(t.get("score"), int)]
    avg = round(sum(scores)/len(scores), 2) if scores else 0.0
    return render_template_string(SUMMARY_HTML, role=st["role"], style=st["style"],
                                  turns=st["turns"], avg=avg)

# --------------------------- inline templates ---------------------------
INDEX_HTML = """
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Interview Coach</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head><body>
<nav class="navbar bg-body-tertiary border-bottom"><div class="container">
  <a class="navbar-brand fw-bold" href="/">★ AI Interview Coach</a>
</div></nav>
<main class="container py-4">
  <div class="row justify-content-center"><div class="col-lg-8">
    <div class="card shadow-sm border-0"><div class="card-body p-4">
      <h1 class="h4 mb-3">Start a Practice Interview</h1>
      <form action="/start" method="post" class="row g-3">
        <div class="col-md-6">
          <label class="form-label fw-semibold">Interview for role</label>
          <input name="role" class="form-control form-control-lg" placeholder="e.g., Data Scientist, Teacher" required>
        </div>
        <div class="col-md-6">
          <label class="form-label fw-semibold">Style</label>
          <select name="style" class="form-select form-select-lg">
            <option>Behavioral</option><option>Situational</option><option>Technical</option>
          </select>
        </div>
        <div class="col-md-6">
          <label class="form-label fw-semibold">Number of questions</label>
          <input type="number" name="num_questions" min="1" max="20" value="5" class="form-control form-control-lg" required>
        </div>
        <div class="col-12 d-flex justify-content-end">
          <button class="btn btn-primary btn-lg px-4">Start Interview</button>
        </div>
      </form>
    </div></div>
  </div></div>
</main>
</body></html>
"""

ASK_HTML = """
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Interview</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head><body>
<nav class="navbar bg-body-tertiary border-bottom"><div class="container">
  <a class="navbar-brand fw-bold" href="/">★ AI Interview Coach</a>
</div></nav>
<main class="container py-4">
  <div class="d-flex align-items-center gap-2 mb-3">
    <span class="badge text-bg-secondary px-3 py-2">{{ style }}</span>
    <span class="badge text-bg-info px-3 py-2">{{ role }}</span>
  </div>
  <div class="progress mb-3" style="height:10px;"><div class="progress-bar" style="width: {{ progress }}%;"></div></div>
  <div class="small text-muted mb-3">Question {{ i + 1 }} of {{ total }}</div>

  {% if last %}
  <div class="card border-0 shadow-sm mb-4"><div class="card-body">
    <h2 class="h6">Feedback on your previous answer</h2>
    <div class="row">
      <div class="col-md-6"><h6 class="fw-semibold">Feedback</h6>
        <ul>{% for f in last.feedback %}<li>{{ f }}</li>{% endfor %}</ul></div>
      <div class="col-md-6"><h6 class="fw-semibold">Improvements</h6>
        <ul>{% for x in last.improvements %}<li>{{ x }}</li>{% endfor %}</ul></div>
    </div>
    <div><span class="fw-semibold">Score:</span> {{ last.score or 0 }}/5</div>
  </div></div>
  {% endif %}

  <div class="card border-0 shadow-sm"><div class="card-body p-4">
    <h2 class="h5">Question</h2>
    <p class="lead">{{ question }}</p>
    <form action="/answer" method="post">
      <div class="mb-3">
        <label class="form-label fw-semibold">Your answer</label>
        <textarea name="answer" rows="6" class="form-control" placeholder="Write your answer here..." required></textarea>
      </div>
      <div class="d-flex justify-content-end"><button class="btn btn-success">Submit answer</button></div>
    </form>
  </div></div>
</main>
</body></html>
"""

SUMMARY_HTML = """
<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Summary</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head><body>
<nav class="navbar bg-body-tertiary border-bottom"><div class="container">
  <a class="navbar-brand fw-bold" href="/">★ AI Interview Coach</a>
</div></nav>
<main class="container py-4">
  <div class="card border-0 shadow-sm mb-4"><div class="card-body p-4">
    <h1 class="h5 mb-0">Interview Summary</h1>
    <div class="text-muted mt-1">{{ style }} for {{ role }}</div>
  </div></div>

  <div class="card border-0 shadow-sm mb-4"><div class="card-body p-4">
    <div class="fw-semibold">Average rating:</div>
    <div class="fs-4">{{ avg }}/5</div>
  </div></div>

  {% for t in turns %}
  <div class="card border-0 shadow-sm mb-3"><div class="card-body">
    <div class="mb-2"><span class="badge text-bg-secondary">Q{{ loop.index }}</span></div>
    <p class="mb-2"><strong>Question:</strong> {{ t.question }}</p>
    <p class="mb-2"><strong>Your answer:</strong><br>{{ t.answer }}</p>
    <div class="row">
      <div class="col-md-6">
        <h6 class="fw-semibold">Feedback</h6>
        <ul class="mb-2">{% for f in t.feedback %}<li>{{ f }}</li>{% endfor %}</ul>
      </div>
      <div class="col-md-6">
        <h6 class="fw-semibold">Improvements</h6>
        <ul class="mb-2">{% for x in t.improvements %}<li>{{ x }}</li>{% endfor %}</ul>
      </div>
    </div>
    <div><span class="fw-semibold">Score:</span> {{ t.score or 0 }}/5</div>
  </div></div>
  {% endfor %}

  <div class="d-flex justify-content-between mt-4">
    <a class="btn btn-outline-secondary" href="/">Start new interview</a>
  </div>
</main>
</body></html>
"""

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
