import unittest
from event import merge_event_handler_dicts

class EventHandlerMergingTestCase(unittest.TestCase):
    def test_non_shared_event_types(self):
        self._given_an_event_handler_dict(
            {"type_1": lambda event: self._called_handler("handler_1")})
        self._given_an_event_handler_dict(
            {"type_2": lambda event: self._called_handler("handler_2")})
        self._given_merged_event_handler_dicts()
        self._when_invoke_merged_event_handler_for_type("type_1")
        self._then_called_handlers_are([
                "handler_1"])

    def test_shared_event_type(self):
        self._given_an_event_handler_dict(
            {"shared_type": lambda event: self._called_handler("handler_1")})
        self._given_an_event_handler_dict(
            {"shared_type": lambda event: self._called_handler("handler_2")})
        self._given_merged_event_handler_dicts()
        self._when_invoke_merged_event_handler_for_type("shared_type")
        self._then_called_handlers_are([
                "handler_1",
                "handler_2"])

    def setUp(self):
        self._event_handler_dicts = []
        self._called_handlers = []

    def _given_an_event_handler_dict(self, event_handler_dict):
        self._event_handler_dicts.append(event_handler_dict)

    def _given_merged_event_handler_dicts(self):
        self._merged_event_handlers = merge_event_handler_dicts(self._event_handler_dicts)

    def _when_invoke_merged_event_handler_for_type(self, event_type):
        merged_event_handler = self._merged_event_handlers[event_type]
        merged_event_handler("mock_event")

    def _called_handler(self, handler):
        self._called_handlers.append(handler)

    def _then_called_handlers_are(self, expected):
        self.assertEqual(expected, self._called_handlers)
