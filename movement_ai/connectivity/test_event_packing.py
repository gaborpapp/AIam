import unittest
import numpy

import sys
sys.path.insert(0, ".")
from .event_packing import EventPacker
from event import Event

class EventPackerTestCase(unittest.TestCase):
    def test_string(self):
        self._test_roundtrip("some content")

    def test_dict(self):
        self._test_roundtrip({"key": "value"})

    def test_list(self):
        self._test_roundtrip([1.0, 1.5])

    def test_float(self):
        self._test_roundtrip(1.0)

    def test_numpy_array(self):
        content = numpy.array([1.0, 1.5])
        event = Event("some type", content)
        unpacked_event = EventPacker.unpack(EventPacker.pack(event))
        self.assertEqual(numpy.ndarray, unpacked_event.content.__class__)
        numpy.testing.assert_array_equal(
            event.content,
            unpacked_event.content)

    def _test_roundtrip(self, content):
        event = Event("some type", content)
        self.assertEqual(event, EventPacker.unpack(EventPacker.pack(event)))
