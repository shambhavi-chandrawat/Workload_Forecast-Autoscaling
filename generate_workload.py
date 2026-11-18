import csv
from datetime import datetime, timezone

# Five workload patterns, expressed as target requests per second.
PATTERNS = {
    "normal":   [3, 4, 4, 5, 4, 3],
    "ramp":     [2, 5, 8, 12, 16, 20],
    "spike":    [3, 3, 4, 20, 22, 4],
    "falling":  [20, 16, 12, 8, 5, 3],
    "variable": [3, 12, 5, 18, 7, 15],
}

def main():
    with open("workload_profile.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["interval", "scenario", "target_rps", "duration_seconds"])
        for scenario, values in PATTERNS.items():
            for i, rps in enumerate(values, 1):
                writer.writerow([i, scenario, rps, 5])
    print("Created workload_profile.csv with 30 workload intervals.")

if __name__ == "__main__":
    main()
