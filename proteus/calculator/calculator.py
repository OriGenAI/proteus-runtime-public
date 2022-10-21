from proteus.calculator.parser import parser


def validate(expr):
    try:
        parser.parse(expr)
        return True
    except Exception:
        return False


def eval(expr, ctx: None):
    eval_chain = parser.parse(expr)
    return eval_chain(ctx)
