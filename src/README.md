## Work division:

Varun: Frontend service, Client Service, Initial Docker setup, Design doc

Pratyush: Catalog service, Order service, Testing, Docker-compose setup, Eval doc 

---

# Part 1

---

## Server

Run the below command to install the requirements for this lab. It uses the [requirements.txt](..%2Frequirements.txt).

`pip install -r ../requirements.txt`



To run the servers native without containerization, we just run the 3 python files [catalog_service.py](catalog%2Fcatalog_service.py), [frontend_service.py](frontend%2Ffrontend_service.py) and [order_service.py](order%2Forder_service.py). The port and the upstream urls are set to default unless provided exclusively via environment variables.

Run the below 3 commands to start the servers:

`python catalog/catalog_service.py`

`python order/order_service.py`

`python frontend/frontend_service.py`

---

## Client
In order to run the client, make sure we have put hostname as localhost:

`python client/MyClient.py`

In order to run multiple clients, run the script [run.sh](client%2Frun.sh) placed in the client directory.

`bash client/run.sh`


---

# Part 2

If we want to run the docker containers individually without the use of `docker-compose.yml`, run [build_individual_containers.sh](..%2Fbuild_individual_containers.sh)

`bash ../build_individual_containers.sh`

Noticing carefully, the environment variables are injected via the Dockerfile which gets run by the bash file.

In order to build and run via [docker-compose.yml](..%2Fdocker-compose.yml), run the below command:

`docker compose up --build`

Client runs the same way as in Part 1.

In order to stop and remove the running containers, run

`docker compose down --remove-orphans`

---

# Running test cases

Run the file [test.py](..%2Ftest%2Ftest.py) using,

`python ../test/test.py`
