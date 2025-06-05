 - Create a ubuntu vm
 - Have atleast 1TB of disks to hold more models 
 - GPU set up will give you speed but will be expensive. Testing with GPU but if use case doesn't require speed then run it on cpu
 - ssh key pair mode for testing - for prod, have password and integrate with key vault


<!-- connect via ssh -->
# ssh -i "C:\Users\b-athirumuru.AME\Work Folders\Downloads\vmagenticworkflow-gpu-selfhost-keypair.pem" azureuser@20.245.235.171
ssh -i "C:\Users\b-athirumuru.AME\Work Folders\Downloads\vmagenticworkflow-gpu-selfhost-ollama_key.pem" azureuser@52.160.85.77

sudo apt update  <!-- to update debian packages -->
sudo apt install python3.12-venv  <!-- to install python vnev package -->
 python3 -m venv prrenv <!-- to create python vnev -->

# Activate the virtual environment
cd prrenv/
source bin/activate
# Install the required packages
pip install langchain langchain-core langgraph langchain-openai pydantic requests PyGithub bandit azure-identity jupyter streamlit
deactivate

#login with github cli
sudo apt install gh
gh auth login
use the tokent that was generated following confluence instructions and connect via ssh


#add system level env variables
cd /etc/profile.d/
sudo vi prrvars.sh
# add the following lines to the file
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

sudo chmod +x /etc/profile.d/prrvars.sh
source /etc/profile.d/prrvars.sh


#download ollama
curl -fsSL https://ollama.com/install.sh | sh
#download model of your choice
eg - llama3.3 70B
ollama run llama3.3
ollama ps - to check if the model is running

# install nvidia drivers
# sudo kmodsign sha512 /var/lib/shim-signed/mok/MOK.priv /var/lib/shim-signed/mok/MOK.der /lib/modules/6.11.0-1014-azure/updates/dkms/nvidia.ko

# open jupyter
cd prrenv/
source bin/activate
jupyter notebook --no-browser --ip=0.0.0.0 --port=8888
Open new cmd prompt and run the following command:
# ssh -L 8888:localhost:8888 -i "C:\Users\b-athirumuru.AME\Work Folders\Downloads\vmagenticworkflow-gpu-selfhost-keypair.pem" azureuser@20.245.235.171
ssh -L 8888:localhost:8888  -i "C:\Users\b-athirumuru.AME\Work Folders\Downloads\vmagenticworkflow-gpu-selfhost-ollama_key.pem" azureuser@52.160.85.77


sudo apt install libnvidia-common-570
sudo apt install libnvidia-gl-570
sudo apt install nvidia-driver-570


