from instructions.AbstractInstruction import AbstractInstruction


class JumpIfEqual(AbstractInstruction):

    def __init__(self):

        self._loopend_ip = 0

    @property
    def loopend_ip(self):

        return self._loopend_ip

    @loopend_ip.setter
    def loopend_ip(self, loopend_ip):

        self._loopend_ip = loopend_ip

    def need_to_have_snapshot(self):

        return False

    def __str__(self):
        return 'JumpWithCondition'

    def execute(self, environment):

        start_index = environment.stack.pop()
        end_index = environment.stack.pop()

        # If it reaches the end of loop
        if start_index >= end_index:

            #Set ip into the loop end ip
            environment.ip = self._loopend_ip