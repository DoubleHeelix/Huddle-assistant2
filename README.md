# Huddle Assistant

A mobile-friendly AI assistant to help with Huddle Playing in the network marketing industry.

## Setup

1. Clone the repo and navigate to it.
2. Create a virtual environment and activate it.
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in your keys.
5. Run the app:
   ```
   streamlit run app.py
   ```

Deployable to Streamlit Cloud for mobile use.

✅ Git Branching + Preview Deployment
Here’s the clean, professional flow:

🧪 1. Create a new branch for your feature
From your terminal:

git checkout -b feature/add-auth-prompt

Now you're working on a separate “sandbox” version of the app.

🧠 2. Make your changes + test locally
Edit your code, run it via Docker:

docker build -t huddle-test .
docker run -p 8501:8501 --env-file .env huddle-test
This keeps your production image (huddle-assistant) clean.

🌐 3. Push your feature branch to GitHub

git add .
git commit -m "Add auth prompt with timeout"
git push origin feature/add-auth-prompt
🚀 4. Create a Preview Deployment on Render
If you added render.yaml, Render lets you:

Go to your service

Click “Manual Deploy → GitHub Branch”

Select feature/add-auth-prompt

This creates a temporary URL just for that branch — no need to mess with main.

✅ Now you can test the new features from your phone, share the link, etc.

✅ 5. When ready: Merge to main

git checkout main
git merge feature/add-auth-prompt
git push origin main
Your Render app will auto-deploy the new version to production (via render.yaml).

