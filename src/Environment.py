from .Stack import Stack

class Environment:

    def __init__(self):
        self._ip = 0
        self._stack = Stack()
        self._globals = {}
        self._heap = {}

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, ip):
        self._ip = ip

    @property
    def stack(self):
        return self._stack
    
    @property
    def globals(self):
        return self._globals

    @property
    def heap(self):
        return self._heap