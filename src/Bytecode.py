class Bytecode:

    def __init__(self):
        self._instructions = []

    def __str__(self):
        return '\n'.join([str(op) for op in self._instructions])

    def size(self):
        return len(self._instructions)

    def add(self, instruction):
        self._instructions.append(instruction)
    
    @property
    def instructions(self):
        return self._instructions