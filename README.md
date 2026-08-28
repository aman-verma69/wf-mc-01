# AI Commerce Agent

An open-ended conversational commerce assistant with deterministic checkout, explicit confirmation, policy gates, Razorpay Test Mode support, and an immutable SQLite audit trail.

## Run it

```bash
python -m venv backend/.venv && source backend/.venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Without `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`, the app uses a clearly labelled verified demo payment so the entire flow is demonstrable offline. Configure both in `backend/.env`/environment to create actual Razorpay Test Mode orders.

## Run gpt-oss-20b locally

Install and start Ollama, then download the model:

```bash
ollama pull gpt-oss:20b
ollama serve
```

Copy `backend/.env.example` to `backend/.env`; it is already configured for Ollama at `http://localhost:11434/v1` with `gpt-oss:20b`. The conversational planner then understands natural requests and context (for example, comparisons, pronouns, quantities, and product references). It only proposes an action: the backend continues to supply catalog facts, validate product IDs, calculate money, enforce explicit approval, and verify payment.

If the local model service is unavailable, a limited safe fallback supports basic search, cart, and checkout commands.
