## Requirements

The movement AI requires Python 3.

It has been tested with Python 3.6 on Linux.

## Installation
It is highly recommended to install the movement AI in a [virtual environment](https://pypi.org/project/virtualenv/).

To install the required Python libraries, run
```
pip install -r requirements/core.txt -r requirements/gui.txt
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
