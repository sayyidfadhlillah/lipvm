from typing import List

from backend.instructions.AbstractInstruction import AbstractInstruction


class EraseValueFromHeap(AbstractInstruction):

    def __init__(self, keys: List[str]):

        self._keys = keys

    def __str__(self):

        return "EraseValueFromHeap"

    def need_to_have_snapshot(self):

        return False

    def execute(self, environment):

        for key in self._keys:

            environment.remove_key_from_heap(key)