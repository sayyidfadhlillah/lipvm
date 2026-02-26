from sys import argv
from sys import argv
from typing import List, Any

from backend.LipVM import LipVM

def source(path: str):
    with open(path, 'r') as file:
        return file.read()

def main(arguments: List[Any]):
    vm = LipVM("languages.statemachine")
    vm.interpreter.interpret(source("conveyor_belt.statemachine"))

if __name__ == '__main__':
    main(argv)
