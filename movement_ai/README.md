## Requirements

The movement AI requires Python 2.7.

The software has been tested on Linux and OSX.

## Installation
It is highly recommended to install the movement AI in a [virtual environment](https://pypi.org/project/virtualenv/).

To install the required Python libraries, run
```
pip install -r requirements/core.txt -r requirements/gui.txt
```

The library PyQt4 and its dependency sip also need to be installed. In a virtualenv, this can e.g. be done by [installing them from source](https://www.riverbankcomputing.com/static/Docs/PyQt4/installation.html#installing-pyqt4). Another option is to install them with
  
```
sudo apt-get install python-qt4-gl
```

and by creating a symlink from Python's global dist-packages to the virtualenv's local site-packages:
```
ln -s /usr/lib/python2.7/dist-packages/PyQt4 (path-to-your-virtualenv)/lib/python2.7/site-packages/
ln -s /usr/lib/python2.7/dist-packages/sip* (path-to-your-virtualenv)/lib/python2.7/site-packages/
```

## Validate installation
When running
```
python dim_reduce.py -p valencia_quaternion_7d_friction --mode=improvise
```

you should see a window with a dancing stick figure, and various controls.
