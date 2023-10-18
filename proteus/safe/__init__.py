from proteus.safe.cypher import SafelyCypherMixin
from proteus.safe.decypher import SafelyDecipherMixin


class Safely(SafelyCypherMixin, SafelyDecipherMixin):
    pass
