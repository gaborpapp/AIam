## Requirements

The movement AI requires Python 3.

It has been tested with Python 3.6 on Linux.

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
Train a model by running
```
python dim_reduce.py -p valencia_quaternion_7d_friction -train
```

You should see the following output:

```
loading BVHs from scenes/valencia_kinect/*.bvh...
ok
creating training data for 286.8s with 10.0 FPS...
created training data with 2868 samples
saving profiles/dimensionality_reduction/valencia_quaternion_7d_friction_backend_only.data...
ok
training model...
ok
probing model...
ok
saving profiles/dimensionality_reduction/valencia_quaternion_7d_friction_backend_only.model...
ok
saving profiles/dimensionality_reduction/valencia_quaternion_7d_friction_backend_only.entity.model...
ok
```

After training the model, you can explore how the model generates movement by running the software with interactive tool: 
```
python dim_reduce.py -p valencia_quaternion_7d_friction --mode=improvise
```

You should now see a window with a dancing stick figure, and various controls.
