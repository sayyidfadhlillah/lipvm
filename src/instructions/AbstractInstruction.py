from abc import ABC


class AbstractInstruction(ABC):

    def __str__(self):

        return 'AbstractInstruction'

    def need_to_have_snapshot(self):

        raise NotImplementedError('a sub-class must implement this method')

    def execute(self, environment):

        raise NotImplementedError('a sub-class must implement this method')