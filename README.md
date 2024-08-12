
![proteusAI](https://github.com/jonfunk21/ProteusAI/assets/74795032/14f3b29e-deb5-4357-af2e-e19618f7e363)



# ProteusAI
ProteusAI is a library for machine learning-guided protein design and engineering. 
The library enables workflows from protein structure prediction, the prediction of 
mutational effects-, and zero-shot prediction of mutational effects.
The goal is to provide state-of-the-art machine learning for protein engineering in a central library.

ProteusAI is primarily powered by [PyTorch](https://pytorch.org/get-started/locally/), 
[scikit-learn](https://scikit-learn.org/stable/), 
and [ESM](https://github.com/facebookresearch/esm) protein language models. 

## Getting started

----
The commands used below are tested on Ubuntu 20.04. Some tweaks can be needed for another OS.

To get started, you need to create a conda environment suitable for running the app. You can do this with the following commands:

```
conda create -n proteusAI_depl python=3.8
conda activate proteusAI_depl
conda install --yes --file requirements.txt
```
PyTorch must be installed separately with the following command:
```
conda install pytorch torchvision -c pytorch
```
Install Shiny Server on Ubuntu 18.04+ (the instructions for other systems are availabe at <a href="https://posit.co/download/shiny-server/?_gl=1*1mdig69*_ga*MTQ1ODYyNTEzMC4xNzE5ODQwMDQy*_ga_8QJS108GF1*MTcxOTg0Mzg4MC4yLjEuMTcxOTg0Mzg4My4wLjAuMA..*_ga_2C0WZ1JHG0*MTcxOTg0Mzg4MC4yLjEuMTcxOTg0Mzg4My4wLjAuMA.." target="_blank">posit.co</a>, please skip the section about R Shiny packages installation) with the following commands:
```
sudo apt-get install gdebi-core
wget https://download3.rstudio.org/ubuntu-18.04/x86_64/shiny-server-1.5.22.1017-amd64.deb
sudo gdebi shiny-server-1.5.22.1017-amd64.deb
```
Edit the default config file `/etc/shiny-server/shiny-server.conf` for Shiny Server (the `sudo` command or root privileges are required):
```
# Use python from the virtual environment to run Shiny apps
python /home/jonfunk/miniforge3/envs/proteusAI_depl/bin/python;

# Instruct Shiny Server to run applications as the user "shiny"
run_as shiny;

# Never delete logs regardless of the their exit code
preserve_logs true;

# Do not replace errors with the generic error message, show them as they are
sanitize_errors false;

# Define a server that listens on port 80
server {
  listen 80;

  # Define a location at the base URL
  location / {

    # Host the directory of Shiny Apps stored in this directory
    site_dir /srv/shiny-server;

    # Log all Shiny output to files in this directory
    log_dir /var/log/shiny-server;

    # When a user visits the base URL rather than a particular application,
    # an index of the applications available in this directory will be shown.
    directory_index on;
  }
}
```
Restart the shiny server with the following command to apply the server configuration changes:
```
sudo systemctl restart shiny-server
```
If you deploy the app on your local machine, be sure that the port 80 is open and not blocked by a firewall. You can check it with `netstat`:
```
nc <your-ip-address> 80
```
If you deploy the app on your Azure Virtual Machine (VM), please add an Inbound Port rule in the <i>Networking - Network Settings</i> section on Azure Portal. Set the following properties:
```
Source: Any
Source port ranges: *
Destination: Any
Service: HTTP
Destination port ranges: 80
Protocol: TCP
Action: Allow
```
Other fields can beleaft as they are by default.

Finally, create symlinks to your app files in the default Shiny Server folder `/srv/shiny-server/`:

```
ln -s /home/jonfunk/ProteusAI/app/app.py /srv/shiny-server/app.py
ln -s /home/jonfunk/ProteusAI/app/logo.png /srv/shiny-server/logo.png
```
If everything has been done correctly, you must see the application index page available at `http://127.0.0.1` (if you deploy your app locally) or at `http://<insert-your-public-VM-IP-address-here>` (if you deploy your app on an Azure VM). Additionally, the remote app can still be available in your local browser (the Shiny extension in Visual Studio must be enabled) if you run the following terminal command on the VM:
```
/home/jonfunk/miniforge3/envs/proteusAI/bin/python -m shiny run --port 33015 --reload --autoreload-port 43613 /home/jonfunk/ProteusAI/app/app.py
```
If you get warnings, debug or "Disconnected from the server" messages, it is likely due to: 
- absent python modules,
- updated versions of the current python modules, 
- using relative paths instead of absolute paths (Shiny Server sees relative paths as starting from `/srv/shiny-server/` folder) 
or 
- logical errors in the code. 

In order to debug the application, see what is written in the server logs under `/var/log/shiny-server` (the log_dir parameter can be reset in the Shiny Server instance config file `/etc/shiny-server/shiny-server.conf`).

## LLM

----

Large language models by Meta are already installed in the proteusAI environment. However, if you also want to use ESM-fold (which requires a good GPU), you can install it as well:

```
pip install 'openfold @ git+https://github.com/aqlaboratory/openfold.git@4b41059694619831a7db195b7e0988fc4ff3a307'
```

Optionally, you can work in Jupyter notebooks if you prefer. To visualize protein structures in Jupyter notebooks, run the following command:
```
jupyter nbextension enable --py widgetsnbextension
```

## External application (MUSCLE for MSA)

----

To run MSA workflows, you need to install the muscle app and download the latest version here: https://github.com/rcedgar/muscle/releases
if you are on a Mac then move the muscle app to the binary folder, and give it the needed permission:

### On Mac
```
mv /path_to_muscle/muscle<version> /usr/local/bin/muscle
chmod -x /usr/local/bin/muscle
```
and Clustalw for DNA MSAs
```
brew install clustal-w
```
