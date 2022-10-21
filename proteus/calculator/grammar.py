from parglare import Grammar
from proteus.calculator.operations import operations, comparisions

e_str = "E: " + "".join(f"{op}\n | " for op in operations.keys())
e_str = e_str.rstrip("\n | ") + ";"

c_str = "C: " + "".join(f"{op}\n | " for op in comparisions.keys())
c_str = c_str.rstrip("\n | ") + ";"

grammar_str = (
    e_str
    + c_str
    + r"""
terminals
number: /\-?\d+(\.\d+)?/;
array: /\$[a-zA-Z_][a-zA-Z0-9_]*/;
"""
)

grammar = Grammar.from_string(grammar_str)
