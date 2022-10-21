from parglare import Parser
from proteus.calculator.grammar import grammar
from proteus.calculator.operations import operations, comparisions


actions = {
    "E": [op for op in operations.values()],
    "C": [op for op in comparisions.values()],
    "number": lambda _, value: float(value),
    "array": lambda _, ref: ref,
}

parser = Parser(grammar, actions=actions)
