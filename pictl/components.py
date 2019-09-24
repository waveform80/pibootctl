from .parser import BOOL_PARAMS

class SPI:
    def __init__(self, config):
        state = BOOL_PARAMS['spi']
        for item in config:
            if isinstance(item, ConfigParam):
                if item.overlay == 'base' and item.param == 'spi':
                    state = item.value
