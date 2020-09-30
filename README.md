# Proof Of Engagement

Whitepaper and models for Proof of Engagement

## Installation

- Install Conda?
- Create environment?
- Python v3.7.9
- `pip install -r requirements.txt`

For Ubuntu:

Add [python 3.7](https://linuxize.com/post/how-to-install-python-3-7-on-ubuntu-18-04/):

```sh
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.7
```

[Install Anaconda](https://phoenixnap.com/kb/how-to-install-anaconda-ubuntu-18-04-or-20-04):

```sh
cd /tmp
curl -O https://repo.anaconda.com/archive/Anaconda3-2020.07-Linux-x86_64.sh
bash Anaconda3-2020.07-Linux-x86_64.sh
```

Open new terminal (re-run ~/.bashrc) and type:

```sh
conda info
conda create --name testing python=3
conda activate testing

# this should be python 3.8
python --version
```

Install deps:

```sh
pip install -r requirements.txt
```

## Running the notebooks

```
jupyter notebook
```
