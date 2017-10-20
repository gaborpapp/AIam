#!/bin/sh

#INTERPRETER_VIEWER_ARGS=--with-viewer

cd ~/projects/AIam/movement_ai
python dim_reduce.py -p valencia_pn_feature_match_z_up --mode=improvise --color-scheme=black --no-toolbar --floor-renderer=checkerboard --websockets --launch-when-ready="gnome-terminal -e 'python interpret_user_movement.py $INTERPRETER_VIEWER_ARGS --tracker=0,-7 --active-area-center=0,3300'"

# force terminal window to stay open
bash
