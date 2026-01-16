class Jump:

    def __init__(self, target_ip):

        self._target_ip = target_ip

    @property
    def target_ip(self):

        return self._target_ip

    def __str__(self):
        return 'Jump'

    def execute(self, environment):

        environment.ip = self._target_ip