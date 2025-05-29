import os
import subprocess
import base64

json_path = "/tmp/google_creds.json"

print("--- ENTRYPOINT SCRIPT STARTED ---") # New debug line

# Decode the base64 secret into a real JSON file
if "GOOGLE_CREDENTIALS_BASE64" in os.environ:
    try:
        decoded_creds = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_BASE64"])
        with open(json_path, "wb") as f:
            f.write(decoded_creds)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path
        print(f"✅ Successfully wrote Google credentials to {json_path}")
    except Exception as e:
        print(f"❌ Error decoding/writing GOOGLE_CREDENTIALS_BASE64: {e}")
else:
    print("⚠️ GOOGLE_CREDENTIALS_BASE64 not found.")

# Fallback to 8501 if PORT is not set
raw_port_from_env = os.getenv("PORT")
print(f"DEBUG: Raw value from os.getenv('PORT'): '{raw_port_from_env}' (Type: {type(raw_port_from_env)})") # New debug line

port = raw_port_from_env
if not port:
    print("❌ PORT environment variable is not set or empty. Defaulting to 8501.")
    port = "8501"
else:
    print(f"✅ Using port: {port}")

# Start memory sync in background
try:
    print("Attempting to start memory_sync.py...")
    subprocess.Popen(["python", "memory_sync.py"])
    print("memory_sync.py Popen called.")
except Exception as e:
    print("⚠️ Memory sync failed to start via Popen:", e)

# Start Streamlit
streamlit_command = [
    "streamlit", "run", "app.py",
    f"--server.port={port}",
    "--server.address=0.0.0.0",
    "--server.enableCORS=false"
]
print(f"Executing Streamlit command: {' '.join(streamlit_command)}") # New debug line
subprocess.run(streamlit_command)
print("--- ENTRYPOINT SCRIPT FINISHED (Streamlit process ended) ---") # New debug line