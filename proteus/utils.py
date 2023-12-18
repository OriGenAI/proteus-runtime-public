import random
import string


def get_random_string(length):
    # Random string with the combination of lower and upper case
    letters = string.ascii_letters
    return "".join(random.choice(letters) for i in range(length))
