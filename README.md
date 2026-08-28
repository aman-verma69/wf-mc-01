# AI Commerce Agent

A focused Razorpay Track 01 MVP: conversational shopping with deterministic checkout, explicit confirmation, policy gates, Razorpay Test Mode support, and an immutable SQLite audit trail.

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

## Demo script

1. Search: `Find ANC headphones under ₹3000`
2. Add SoundMax Pro, then choose **Prepare checkout**.
3. Reply `Confirm` to complete the safe demo payment (or open Razorpay checkout when test keys are configured).
4. For the failure path, prepare a new checkout at ₹2499, select **Simulate price change**, then reply `Confirm`. The policy engine blocks it and invalidates the prior authorization.
