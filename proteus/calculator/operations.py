import numpy as np
import re
import math


def _get(ref, ctx):
    if re.match(r"\$[a-zA-Z_]\w*", str(ref)):
        return ctx.get(ref[1:])
    elif re.match(r"\-?\d+(\.\d+)?", str(ref)):
        return ref
    else:
        return ref(ctx)


operations = {
    "E '+' E  {left, 2}": lambda _, n: lambda ctx: _get(n[0], ctx) + _get(n[2], ctx),
    "E '-' E  {left, 2}": lambda _, n: lambda ctx: _get(n[0], ctx) - _get(n[2], ctx),
    "E '*' E  {left, 3}": lambda _, n: lambda ctx: _get(n[0], ctx) * _get(n[2], ctx),
    "E '/' E  {left, 3}": lambda _, n: lambda ctx: _get(n[0], ctx) / _get(n[2], ctx),
    "'Sin' '(' E ')'  {right, 1}": lambda _, n: lambda ctx: np.sin(_get(n[2], ctx)),
    "'Cos' '(' E ')'  {right, 1}": lambda _, n: lambda ctx: np.cos(_get(n[2], ctx)),
    "'Tan' '(' E ')'  {right, 1}": lambda _, n: lambda ctx: np.tan(_get(n[2], ctx)),
    "'Log' '(' E ')'  {right, 1}": lambda _, n: lambda ctx: np.log10(_get(n[2], ctx)),
    "'Pow' '(' E ',' E ')' {left, 4}": lambda _, n: lambda ctx: np.power(_get(n[2], ctx), _get(n[4], ctx)),
    "'Exp' '(' E ')'  {right, 1}": lambda _, n: lambda ctx: math.e ** _get(n[2], ctx),
    "'If' '(' C ',' E ',' E ')' {right, 1}": lambda _, n: lambda ctx: np.where(
        _get(n[2], ctx), _get(n[4], ctx), _get(n[6], ctx)
    ),
    "'(' E ')'": lambda _, n: lambda ctx: _get(n[1], ctx),
    "number": lambda _, n: n[0],
    "array": lambda _, n: n[0],
}

comparisions = {
    "E '<' E {left, 2}": lambda _, n: lambda ctx: _get(n[0], ctx) < _get(n[2], ctx),
    "E '=' E {left, 2}": lambda _, n: lambda ctx: _get(n[0], ctx) == _get(n[2], ctx),
    "E '>' E {left, 2}": lambda _, n: lambda ctx: _get(n[0], ctx) > _get(n[2], ctx),
    "E '<=' E {left, 2}": lambda _, n: lambda ctx: _get(n[0], ctx) <= _get(n[2], ctx),
    "E '>=' E {left, 2}": lambda _, n: lambda ctx: _get(n[0], ctx) >= _get(n[2], ctx),
    "E '<>' E {left, 2}": lambda _, n: lambda ctx: _get(n[0], ctx) != _get(n[2], ctx),
    "C 'Or' C {left, 2}": lambda _, n: lambda ctx: np.logical_or(_get(n[0], ctx), _get(n[2], ctx)),
    "C 'And' C {left, 2}": lambda _, n: lambda ctx: np.logical_and(_get(n[0], ctx), _get(n[2], ctx)),
}
