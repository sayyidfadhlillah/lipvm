from languages.minilogo.syntax.LanguageParser import LanguageParser


class Expression:

    def __init__(self, expression_context: LanguageParser.ExpressionContext):

        self._expression_context = expression_context

    @property
    def expression_context(self):

        return self._expression_context

    def __str__(self):
        return 'Expression'

    def execute(self, environment):

        #TODO Implement, evaluate expression
        pass