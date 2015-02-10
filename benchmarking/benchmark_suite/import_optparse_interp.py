try:
    import __pyston__
    __pyston__.setOption("FORCE_INTERPRETER", 1)
except ImportError:
    pass

import optparse
