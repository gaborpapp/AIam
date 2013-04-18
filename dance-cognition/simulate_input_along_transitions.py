from simple_osc_sender import OscSender
from states import state_machine, InterStatePosition
import time
import random
from stopwatch import Stopwatch
from vector import Vector3d

SPEED = 1.0

def noise():
    return Vector3d(
        random.uniform(-1.0, 1.0),
        random.uniform(-1.0, 1.0),
        random.uniform(-1.0, 1.0)) * 0.01

osc_sender = OscSender(50001)
stopwatch = Stopwatch()

source_state = random.choice(state_machine.states.values())
while True:
    destination_state = random.choice(source_state.outputs + source_state.inputs)
    print "%s -> %s" % (source_state.name, destination_state.name)
    inter_state_position = InterStatePosition(source_state, destination_state, 0.0)
    distance = (destination_state.position - source_state.position).mag()
    duration = distance / SPEED
    stopwatch.restart()
    while stopwatch.get_elapsed_time() < duration:
        inter_state_position.relative_position = stopwatch.get_elapsed_time() / duration
        p = state_machine.inter_state_to_euclidian_position(inter_state_position)
        p += noise()
        osc_sender.send("/input_position", *p)
        time.sleep(0.01)
    source_state = destination_state
