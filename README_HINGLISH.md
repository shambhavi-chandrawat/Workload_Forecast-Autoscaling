# Workload Forecasting for Autoscaling — Ready-to-run package

Ye package tumhare existing GitHub project ko replace nahi karta. Isko ek **separate experiment folder** ke roop mein use karo. Isme apna generated workload, Docker-based baseline, Docker Swarm forecast-based scaling, aur CSV results hain.

## Project ka simple idea

- **VM1 (Baseline):** Flask application ka ek fixed Docker container. Is VM par `baseline` experiment chalega.
- **VM2 (Forecast):** Wahi Flask application Docker Swarm service mein chalegi. Python script demand forecast karke replicas 1 se 4 tak scale karegi.
- Dono VMs par same workload patterns run honge: normal, ramp-up, sudden spike, falling aur variable.
- Results mein CPU, memory, average response time, throughput, failed requests aur active replicas record honge.

> Important: Ye application/container-level horizontal autoscaling demo hai. Ye VirtualBox ke VMs ko khud create/delete ya resize nahi karta.

## Part A — Files VM par bhejna

ZIP ko Mac par extract karo. Extracted folder ke andar ye files hongi.

Mac Terminal mein extracted folder ke andar jaakar (example path apne hisaab se badalna):
```bash
cd ~/Downloads/Autoscaling_Project_Ready
scp -P 2222 app.py Dockerfile requirements.txt generate_workload.py experiment.py setup_baseline.sh setup_forecast.sh ubuntu@127.0.0.1:~/autoscaling-app/
```

Agar VM ka SSH port alag hai, `2222` ko apne configured port se replace karna.

VM par SSH login karke:
```bash
cd ~/autoscaling-app
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
chmod +x setup_baseline.sh setup_forecast.sh
python3 generate_workload.py
```

## Part B — VM1: Baseline run

VM1 par:
```bash
cd ~/autoscaling-app
./setup_baseline.sh
curl http://localhost:5000/health
sudo .venv/bin/python experiment.py --mode baseline
```
Results `results_baseline.csv` mein save honge.

Experiment ke baad server band karne ke liye:
```bash
sudo docker rm -f baseline-server
```

## Part C — VM2: Forecast autoscaling run

VM2 par same files transfer karke dependencies install karo (Part A). Phir:
```bash
cd ~/autoscaling-app
./setup_forecast.sh
curl http://localhost:5000/health
sudo .venv/bin/python experiment.py --mode forecast
```
Results `results_forecast.csv` mein save honge.

Forecast mode mein Docker Swarm service 1–4 replicas ke beech scale hoti hai. Scaling decisions recent workload demand ke Holt-style level/trend forecast par based hain.

## Part D — Results Mac par wapas copy karna

Mac Terminal se:
```bash
scp -P 2222 ubuntu@127.0.0.1:~/autoscaling-app/results_baseline.csv .
```
Forecast VM ke liye us VM ka SSH port use karke:
```bash
scp -P YOUR_VM2_SSH_PORT ubuntu@127.0.0.1:~/autoscaling-app/results_forecast.csv .
```

## Important troubleshooting

- `ModuleNotFoundError`: VM par `.venv/bin/pip install -r requirements.txt` dobara run karo.
- `Address already in use`: purana container/service port 5000 use kar raha hai. `sudo docker ps` aur `sudo docker service ls` check karo.
- Docker permission issue: commands mein `sudo` use karo.
- `docker swarm init` error that Swarm is already active: script is designed to continue if it is already initialized.
- VM2 ko VM1 ke same time par run mat karna; 8 GB Mac par VMs ko sequentially run karna better hai.
- Baseline aur forecast results same machine load, same VM RAM/CPU settings, aur same workload profile ke saath compare karo.

## Viva mein kaise explain karna hai

"Humne apna synthetic workload dataset generate kiya jisme normal, ramp-up, spike, falling aur variable traffic patterns hain. Baseline VM par application ek fixed replica ke saath run hoti hai. Forecast VM par recent workload demand se Holt-style trend forecast nikal kar Docker Swarm replicas 1 se 4 ke beech adjust karta hai. Dono modes mein same workload run karke CPU, memory, response time, throughput aur failed requests compare karte hain."

## Files

- `app.py` — Flask web application
- `Dockerfile` — Docker image build instructions
- `generate_workload.py` — workload profile CSV generator
- `experiment.py` — workload execution, monitoring, forecasting and result collection
- `setup_baseline.sh` — fixed single-container deployment
- `setup_forecast.sh` — Docker Swarm deployment for scaling
- `requirements.txt` — Python dependencies
