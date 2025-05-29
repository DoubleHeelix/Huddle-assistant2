import os
import subprocess

# Optionally run memory sync
try:
    subprocess.Popen(["python", "memory_sync.py"])
except Exception as e:
    print("⚠️ Memory sync failed to start:", e)

# Get port from Railway or fallback to 8501
port = os.getenv("PORT", "8501")

# Launch Streamlit
subprocess.run([
    "streamlit", "run", "app.py",
    f"--server.port={port}",
    "--server.address=0.0.0.0",
    "--server.enableCORS=false"
])
