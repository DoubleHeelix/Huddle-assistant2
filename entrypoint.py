import os
import subprocess

# Fallback to 8501 if PORT is not set
port = os.getenv("PORT")
if not port:
    print("❌ PORT environment variable is not set. Defaulting to 8501.")
    port = "8501"
else:
    print(f"✅ Using port: {port}")

# Start memory sync in background
try:
    subprocess.Popen(["python", "memory_sync.py"])
except Exception as e:
    print("⚠️ Memory sync failed to start:", e)

# Start Streamlit
subprocess.run([
    "streamlit", "run", "app.py",
    f"--server.port={port}",
    "--server.address=0.0.0.0",
    "--server.enableCORS=false"
])
