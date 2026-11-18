from flask import Flask, jsonify
import os, socket, time

app = Flask(__name__)

@app.get("/")
def home():
    return jsonify(message="Autoscaling project server is running", host=socket.gethostname())

@app.get("/health")
def health():
    return jsonify(status="healthy", host=socket.gethostname())

@app.get("/work")
def work():
    # Small CPU task to create measurable server workload during the experiment.
    start = time.perf_counter()
    duration = float(os.getenv("WORK_SECONDS", "0.03"))
    value = 0
    while time.perf_counter() - start < duration:
        value = (value * 1664525 + 1013904223) % 4294967296
    return jsonify(status="success", host=socket.gethostname(), result=value)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
