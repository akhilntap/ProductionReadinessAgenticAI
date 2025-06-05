

Install packages
sudo apt-get install docker-ce docker-ce-cli containerd.io
sudo apt-get install apt-transport-https ca-certificates curl software-properties-common
Note: If docker repo is not set up, the above installation will fail. Steps to resolve
Steps to Resolve

1. Update System Packages

First, update your system's package list to ensure you have the latest information.
`
sudo apt-get update
2. Add Docker's GPG Key

Add Docker's official GPG key to your system.

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
3. Set Up the Docker Repository

Add the Docker repository to your system's sources list.

echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
4. Update Package List Again

Update the package list again to include the Docker repository.

sudo apt-get update
5. Install Docker-CE

Finally, install Docker-CE and its dependencies.

sudo apt-get install docker-ce docker-ce-cli containerd.io


create a new direcotry and save the foollowing to pyproject.toml
[tool.poetry]
name = "llm-streamlit-app"
version = "0.1.0" 
description = "LLM-Powered Streamlit App"
authors = ["Akhil Reddy Thirumuru akhilred@netapp.com"] 

[build-system]
requires = ["poetry-core>=1.0.0"] 
build-backend = "poetry.core.masonry.api" 

[tool.poetry.dependencies] 
python = "^3.8"
Streamlit = "^0.85.0" 
transformers = "^4.10.3" 

[tool.poetry.dev-dependencies] 

[build-system]
requires = ["poetry-core>=1.0.0"] 
build-backend = "poetry.core.masonry.api"






linux non-debian package installation
create a new directory for venv - python3 -m venv path/to/venv
use path/to/venv/bin/python TO RUN PYTHON ( /home/azureuser/streamlit_env/bin/python)
uSE  path/to/venv/bin/pip install package name TO INSTALL PACKAGE  ( /home/azureuser/streamlit_env/bin/pip install streamlit)


dockerize
# Use an official Python runtime as a parent ima # Use an official Python runtime as a parent ima 
FROM python:3.11-slim-buster 
# Set the working directory to /app 
WORKDIR /app
# Copy the Current directory contents into the container at /app
COPY. /app
# Install any needed packages specified in requi 
RUN /home/azureuser/streamlit_env/bin/pip install poetry 
COPY pyproject.toml poetry.lock /app/
RUN poetry install --no-dev 
# Make port 8501 available to the world outside this container
EXPOSE 8501
# Define environment variable 
ENV NAME World 
# Run Streamlit when the container launches 
CMD ["streamlit", "run", "streamlitapp.py"]

 /home/azureuser/streamlit_env/bin/python -m  streamlit run /home/azureuser/prr/streamlit.py



To access jupyter notebook, run the following command in the terminal:
cd streamlit_env/
source bin/activate
jupyter notebook --no-browser --ip=0.0.0.0 --port=8888
Copy the token printed at the end of address
Open new cmd prompt and run the following command:
ssh -L 8888:localhost:8888 -i "C:\Users\b-athirumuru.AME\Work Folders\Downloads\vmagenticworkflow_key.pem" azureuser@104.209.4.91
open broweser and go to http://localhost:8888
Paste the token that was previously copied


Prometheus perms
Monitoring reader is to be given for UMI for rg since alert rules are at rg level and not monitor level


to add system wide env vars
 cd /etc/profile.d/
 sudo vi myenvvars.sh



gpu
cd /home/agenticvm/prrenv

Hit:1 http://azure.archive.ubuntu.com/ubuntu noble InRelease
Hit:2 http://azure.archive.ubuntu.com/ubuntu noble-updates InRelease
Hit:3 http://azure.archive.ubuntu.com/ubuntu noble-backports InRelease
Hit:4 http://azure.archive.ubuntu.com/ubuntu noble-security InRelease
Hit:5 https://download.docker.com/linux/ubuntu noble InRelease

sudo add-apt-repository ppa:chris-lea/munin-plugins
