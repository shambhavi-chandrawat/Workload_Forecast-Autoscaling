import argparse
import csv
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from statistics import mean

import psutil
import requests

PATTERNS = {
    "normal": [3, 4, 4, 5, 4, 3],
    "ramp": [2, 5, 8, 12, 16, 20],
    "spike": [3, 3, 4, 20, 22, 4],
    "falling": [20, 16, 12, 8, 5, 3],
    "variable": [3, 12, 5, 18, 7, 15],
}
DURATION = 5
URL = "http://127.0.0.1:5000/work"
REQUEST_TIMEOUT_SECONDS = 5
CPU_SAMPLE_SECONDS = 0.5
SCALE_TIMEOUT_SECONDS = 40


def request_once():
    started = time.perf_counter()
    try:
        response = requests.get(URL, timeout=REQUEST_TIMEOUT_SECONDS)
        latency = time.perf_counter() - started
        if response.status_code == 200:
            return latency, True, ""
        return latency, False, "http_error"
    except requests.Timeout:
        return time.perf_counter() - started, False, "timeout"
    except requests.ConnectionError:
        return time.perf_counter() - started, False, "connection_error"
    except requests.RequestException:
        return time.perf_counter() - started, False, "request_error"


def forecast_next(values):
    if not values:
        return 1.0
    alpha, beta = 0.6, 0.3
    level = float(values[0])
    trend = float(values[1] - values[0]) if len(values) > 1 else 0.0
    for value in values[1:]:
        old_level = level
        level = alpha * float(value) + (1 - alpha) * (level + trend)
        trend = beta * (level - old_level) + (1 - beta) * trend
    return max(0.0, level + trend)


def get_service_running_replicas():
    output = subprocess.check_output(
        ["sudo", "docker", "service", "ls",
         "--filter", "name=forecast-app", "--format", "{{.Replicas}}"],
        text=True,
    ).strip()
    if not output or "/" not in output:
        return 0, 0
    running, desired = output.split("/", 1)
    return int(running), int(desired)


def docker_scale(replicas):
    subprocess.run(
        ["sudo", "docker", "service", "scale", f"forecast-app={replicas}"],
        check=True,
    )
    deadline = time.monotonic() + SCALE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            running, desired = get_service_running_replicas()
            if running == replicas and desired == replicas:
                print(f"Swarm service ready: {running}/{desired} replicas")
                return
        except (subprocess.CalledProcessError, ValueError):
            pass
        time.sleep(1)
    running, desired = get_service_running_replicas()
    raise RuntimeError(
        f"Swarm did not reach {replicas}/{replicas} replicas within "
        f"{SCALE_TIMEOUT_SECONDS}s. Current state: {running}/{desired}"
    )


def get_replicas(mode):
    if mode == "baseline":
        return 1
    try:
        running, _ = get_service_running_replicas()
        return running
    except Exception:
        return 0


def resource_monitor(stop_event, cpu_samples, memory_samples):
    psutil.cpu_percent(interval=None)
    while not stop_event.wait(CPU_SAMPLE_SECONDS):
        cpu_samples.append(psutil.cpu_percent(interval=None))
        memory_samples.append(psutil.virtual_memory().percent)


def run_rate_limited_workload(target_rps):
    total_requests = target_rps * DURATION
    max_workers = max(10, min(100, target_rps * 3))
    latencies = []
    successes = 0
    failure_counts = {
        "timeout": 0,
        "connection_error": 0,
        "http_error": 0,
        "request_error": 0,
    }

    cpu_samples = []
    memory_samples = []
    stop_monitor = threading.Event()
    monitor = threading.Thread(
        target=resource_monitor,
        args=(stop_monitor, cpu_samples, memory_samples),
        daemon=True,
    )
    monitor.start()

    interval_started = time.perf_counter()
    futures = []
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for request_number in range(total_requests):
                scheduled_time = interval_started + (request_number / target_rps)
                delay = scheduled_time - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                futures.append(pool.submit(request_once))

            for future in as_completed(futures):
                latency, ok, failure_type = future.result()
                latencies.append(latency)
                if ok:
                    successes += 1
                elif failure_type in failure_counts:
                    failure_counts[failure_type] += 1
    finally:
        stop_monitor.set()
        monitor.join()

    elapsed = time.perf_counter() - interval_started
    cpu_average = mean(cpu_samples) if cpu_samples else 0.0
    memory_average = (
        mean(memory_samples) if memory_samples else psutil.virtual_memory().percent
    )
    average_latency = mean(latencies) if latencies else 0.0
    throughput = successes / elapsed if elapsed > 0 else 0.0

    return {
        "total_requests": total_requests,
        "successes": successes,
        "failures": total_requests - successes,
        "cpu_average": cpu_average,
        "memory_average": memory_average,
        "average_latency": average_latency,
        "throughput": throughput,
        "elapsed": elapsed,
        "failure_counts": failure_counts,
    }


def run_scenario(mode, scenario, writer):
    history = []
    for interval, target_rps in enumerate(PATTERNS[scenario], 1):
        predicted = forecast_next(history)
        if mode == "forecast":
            desired = max(1, min(4, int((predicted + 5) // 6)))
            docker_scale(desired)

        replicas = get_replicas(mode)
        result = run_rate_limited_workload(target_rps)

        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "scenario": scenario,
            "interval": interval,
            "target_rps": target_rps,
            "forecast_rps": round(predicted, 2),
            "active_replicas": replicas,
            "cpu_percent": round(result["cpu_average"], 2),
            "memory_percent": round(result["memory_average"], 2),
            "avg_response_time_ms": round(result["average_latency"] * 1000, 2),
            "throughput_success_rps": round(result["throughput"], 2),
            "successful_requests": result["successes"],
            "failed_requests": result["failures"],
            "timeout_requests": result["failure_counts"]["timeout"],
            "connection_errors": result["failure_counts"]["connection_error"],
            "http_errors": result["failure_counts"]["http_error"],
            "other_request_errors": result["failure_counts"]["request_error"],
        })
        history.append(target_rps)

        print(
            f"{scenario:8} interval {interval}/6 | target {target_rps:2} rps | "
            f"replicas {replicas} | CPU avg {result['cpu_average']:5.1f}% | "
            f"latency {result['average_latency'] * 1000:6.1f} ms | "
            f"success {result['successes']}/{result['total_requests']} | "
            f"failed {result['failures']} | elapsed {result['elapsed']:.1f}s"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "forecast"], required=True)
    args = parser.parse_args()

    if args.mode == "forecast":
        check = subprocess.run(
            ["sudo", "docker", "service", "inspect", "forecast-app"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if check.returncode != 0:
            raise SystemExit(
                "forecast-app Docker Swarm service not found. "
                "Run setup_forecast.sh first."
            )

    # Separate filenames preserve the original first-run CSV files.
    filename = f"results_{args.mode}_corrected.csv"
    fields = [
        "timestamp", "mode", "scenario", "interval", "target_rps",
        "forecast_rps", "active_replicas", "cpu_percent", "memory_percent",
        "avg_response_time_ms", "throughput_success_rps",
        "successful_requests", "failed_requests", "timeout_requests",
        "connection_errors", "http_errors", "other_request_errors",
    ]

    with open(filename, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for scenario in PATTERNS:
            run_scenario(args.mode, scenario, writer)
            file.flush()

    print(f"\nCorrected results saved to {filename}")


if __name__ == "__main__":
    main()
