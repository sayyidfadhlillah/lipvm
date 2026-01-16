class Increase:

    def __str__(self):

        return 'Increase'

    def execute(self, environment):

        curr_value = environment.stack.pop()
        environment.stack.push(curr_value+1)