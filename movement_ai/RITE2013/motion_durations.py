import collections

MOTION_DURATIONS = [
    ('hb', 'mb', 3.75),
    ('hb', 'mc', 3.125),
    ('hb', 'ml', 4.08333),
    ('hb', 'mlb', 6.20833),
    ('hb', 'mlf', 6.83333),
    ('mb', 'hb', 3.70833),
    ('mb', 'mc', 4.91667),
    ('mb', 'ml', 5.66667),
    ('mb', 'mlb', 4.83333),
    ('mb', 'mlf', 8.5),
    ('mc', 'hb', 3.58333),
    ('mc', 'mb', 4.33333),
    ('mc', 'ml', 2.95833),
    ('mc', 'mlb', 4.83333),
    ('mc', 'mlf', 8.45833),
    ('ml', 'hb', 8.83333),
    ('ml', 'mb', 4.66667),
    ('ml', 'mc', 5.5),
    ('ml', 'mlb', 5.29167),
    ('ml', 'mlf', 5.29167),
    ('mlb', 'hb', 4.04167),
    ('mlb', 'mb', 4.70833),
    ('mlb', 'mc', 5.16667),
    ('mlb', 'ml', 5.75),
    ('mlb', 'mlf', 10.0417),
    ('mlf', 'hb', 6.125),
    ('mlf', 'mb', 6.41667),
    ('mlf', 'mc', 6.83333),
    ('mlf', 'ml', 5.29167),
    ('mlf', 'mlb', 8.95833),
]

DEFAULT_DURATION = 3.0

_durations = collections.defaultdict(dict)
for source_state_name, destination_state_name, duration in MOTION_DURATIONS:
    _durations[source_state_name][destination_state_name] = duration

def get_duration(source_state, destination_state):
    try:
        return _durations[source_state.name][destination_state.name] * 0.5
    except KeyError:
        print("WARNING: failed to get duration for %s->%c" % (
            source_state.name, destination_state.name))
        return DEFAULT_DURATION
