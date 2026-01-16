from typing import List


class EraseValueFromHeap:

    def __init__(self, keys: List[str]):

        self._keys = keys

    def __str__(self):

        return "EraseValueFromHeap"

    def execute(self, environment):

        for key in self._keys:

            environment.remove_key_from_heap(key)