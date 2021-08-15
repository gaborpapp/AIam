class Event:
    SUBSCRIBE = "SUBSCRIBE"
    START = "START"
    STOP = "STOP"
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    REDUCTION = "REDUCTION"
    PARAMETER = "PARAMETER"
    SET_CURSOR = "SET_CURSOR"
    IMPROVISE_PATH = "IMPROVISE_PATH"
    MODE = "MODE"
    CURSOR = "CURSOR"
    VELOCITY = "VELOCITY"
    START_EXPORT_BVH = "START_EXPORT_BVH"
    STOP_EXPORT_BVH = "STOP_EXPORT_BVH"
    BVH_INDEX = "BVH_INDEX"
    PROCEED_TO_NEXT_FRAME = "PROCEED_TO_NEXT_FRAME"
    FEATURES = "FEATURES"
    TARGET_FEATURES = "TARGET_FEATURES"
    TARGET_REDUCTION = "TARGET_REDUCTION"
    FEATURE_MATCH_RESULT = "FEATURE_MATCH_RESULT"
    FEATURE_MATCH_OUTPUT = "FEATURE_MATCH_OUTPUT"
    TARGET_ROOT_VERTICAL_ORIENTATION = "TARGET_ROOT_VERTICAL_ORIENTATION"
    NEIGHBORS_CENTER = "NEIGHBORS_CENTER"
    USER_INTENSITY = "USER_INTENSITY"
    SYSTEM_STATE_CHANGED = "SYSTEM_STATE_CHANGED"
    SAVE_STUDENT = "SAVE_STUDENT"
    LOAD_STUDENT = "LOAD_STUDENT"
    REDUCTION_RANGE = "REDUCTION_RANGE"
    NORMALIZED_OBSERVED_REDUCTIONS = "NORMALIZED_OBSERVED_REDUCTIONS"
    SET_IO_BLENDING_AMOUNT = "SET_IO_BLENDING_AMOUNT"
    IO_BLENDING_AMOUNT = "IO_BLENDING_AMOUNT"
    IO_BLEND = "IO_BLEND"
    SET_IO_BLENDING_USE_ENTITY_SPECIFIC_INTERPOLATION = "SET_IO_BLENDING_USE_ENTITY_SPECIFIC_INTERPOLATION"
    SET_IO_BLENDING_CONTROL_FRICTION = "SET_IO_BLENDING_CONTROL_FRICTION"
    FRAME_COUNT = "FRAME_COUNT"
    SET_FRICTION = "SET_FRICTION"
    SET_LEARNING_RATE = "SET_LEARNING_RATE"
    SET_MODEL_NOISE_TO_ADD = "SET_MODEL_NOISE_TO_ADD"
    SET_MEMORIZE = "SET_MEMORIZE"
    RECALL = "RECALL"
    SET_INPUT_DELAY = "SET_INPUT_DELAY"
    SET_MIN_TRAINING_LOSS = "SET_MIN_TRAINING_LOSS"
    TRAINING_LOSS = "TRAINING_LOSS"
    SET_MAX_ANGULAR_STEP = "SET_MAX_ANGULAR_STEP"

    def __init__(self, type_, content=None):
        self.type = type_
        self.content = content
        self.source = None

    def __str__(self):
        return "Event(%r, %r, source=%s)" % (self.type, self.content, self.source)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return self.type == other.type and self.content == other.content

    def __ne__(self, other):
        return not (self == other)

    def __getstate__(self):
        return (self.type, self.content)

    def __setstate__(self, state):
        self.type, self.content = state

def merge_event_handler_dicts(event_handler_dicts):
    event_types = _get_all_event_types(event_handler_dicts)
    return dict(
        (event_type, _get_merged_event_handlers_for_type(event_handler_dicts, event_type))
        for event_type in event_types)

def _get_all_event_types(event_handler_dicts):
    result = set()
    for event_handler_dict in event_handler_dicts:
        result.update(list(event_handler_dict.keys()))
    return result

def _get_merged_event_handlers_for_type(event_handler_dicts, event_type):
    handlers = _get_all_handlers_of_type(event_handler_dicts, event_type)
    if len(handlers) == 1:
        return handlers[0]
    else:
        def merged_handler(event):
            for handler in handlers:
                handler(event)
        return lambda event: merged_handler(event)

def _get_all_handlers_of_type(event_handler_dicts, event_type):
    return [
        event_handler_dict[event_type]
        for event_handler_dict in event_handler_dicts
        if event_type in event_handler_dict]
