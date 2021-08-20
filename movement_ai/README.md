## Pose mapping
This software deals with analysis and automatic generation of dance movements. The software implements [pose mapping](https://www.ijcai.org/Proceedings/15/Papers/344.pdf), a statistical approach which assumes that human dancers have a style or repertoire which can be characterized as a tendency to perform certain poses. By recording and analyzing a dancer’s movements and creating a statistical model of them, we assume that the dancer’s style – the "signal" in the data – can be  captured, at least to some extent. This model can then serve as a basis for exploring novel variations of observed movements.

For purposes of simplification, we focus on the postural content of movements rather than their temporal dynamics. In other words, the statistical analysis only deals with how limbs and joints are configured in particular moments, rather than how poses within a movement develop over time.

## Requirements
The movement AI requires Python 3.

It has been tested with Python 3.6 and 3.8 on Linux.

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

## Improvisation mode
In the improvisation mode, the system automatically explores the contents of a pose map, thereby synthesizing novel movements. The method generates trajectories across the pose map as smoothly interpolated curves.
 
Below is a description of some of the improvisation parameters:

* **novelty**: Tendency to explore unobserved regions in the pose map, i.e. regions with poses that haven't been observed in the training data. Higher novelty causes more "creative" movements.
* **extension**: Preferred length of trajectories. Higher extension causes more "creative" movements.
* **velocity**: Speed of movement.
* **location_preference**: Tendency to prefer a default pose, e.g. an idle pose. The default pose is specified with the `--preferred-location` argument.
