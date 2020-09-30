# Proof Of Engagement

Whitepaper and models for Proof of Engagement

## Prerequisites

The models in this repo have been developed using Python v3.8 and may or may not work with older versions of Python v3. You can use a system-wide installation of Python, but it is recommended to use a virtual environment such as [virtualenv](https://virtualenv.pypa.io/en/latest/) or [Anaconda](https://docs.anaconda.com/anaconda/).

### Installing Python system-wide

The best way to install Python will depend on your system. As an example, to install Python on Ubuntu via `apt` you can run the following:

```sh
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.8
python --version # should print Python 3.8.5 (or similar)
```

See other options [here](https://wiki.python.org/moin/BeginnersGuide/Download).

### Installing Python via Anaconda

Follow the instructions [here](https://docs.anaconda.com/anaconda/install/) to install Anaconda on your system. For example on Ubuntu using `bash` you can run the following:

```sh
cd /tmp
curl -O https://repo.anaconda.com/archive/Anaconda3-2020.07-Linux-x86_64.sh
# recommended: verify integrity using hashes from https://docs.anaconda.com/anaconda/install/hashes/
bash Anaconda3-2020.07-Linux-x86_64.sh
source ~/.bashrc
```

Then to create a new environment run the following:

```sh
conda create --name proof-of-engagement python=3.8
conda activate proof-of-engagement
python --version # should print Python 3.8.5 (or similar)
```

## Installation

In the root directory run the following:

```sh
pip install -r requirements.txt
```

Depending on your setup you may need to specify that you want to use `pip` for Python v3 instead:

```sh
pip3 install -r requirements.txt
```

## Running the notebooks

Run the following command:

```sh
jupyter notebook
```

It should open up a tab in your default browser from which you can navigate to and run the various notebooks.
