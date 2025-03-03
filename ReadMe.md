# TailDropGUI

## About

I made this simple GUI to help me when using tailscale between Linux and other devices. It's a simple program that lets you drag and drop files to send to devices online on your tailnet. 

## Installation

You can install the requirements by running `pip install -r requirements.txt`. It is however recommended to use a virtual environment or a conda environment to avoid conflicts with other packages.

If you want to run it more like a command or program, you can create a bash script like the one below (the example uses conda):

```bash
#!/bin/bash

# Run gui.py in the background using the Conda environment
conda run --no-capture-output -n conda_env python ~/yourpathhere/taildropgui.py > ~/yourpathhere/gui_output.log 2>&1 &

# Print the PID of the background process
echo "GUI started with PID: $! \nYou can kill using \"kill < $ >\" or pkill -f taildropgui.py"
```

And run 

```bash
chmod +x taildropgui.sh
```

to make it executable.

Note, because tailscale requires sudo to run, you may have to do the following:
  
```bash
sudo visudo
```

and add:

```bash
yourusername ALL=(ALL) NOPASSWD: /usr/bin/tailscale file cp *
yourusername ALL=(ALL) NOPASSWD: /usr/bin/tailscale file get *
```

## Usage

Once launched, it will open a window and you can select the device to send to from the drop down. You can also select the folder to save the files to. Then, simply select or drop a file to send, or click the receive files button to receive files from taildrop.

## Credits:

The icons are from SVG repo
