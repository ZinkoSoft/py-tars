# epdconfig.py — libgpiod v1/v2 compatible, spidev chunked writes
import time, spidev
import gpiod

GPIO_CHIP = "/dev/gpiochip3"
RST_PIN  = (GPIO_CHIP, 1)     # GPIO3_A1
BUSY_PIN = (GPIO_CHIP, 10)    # GPIO3_B2
DC_PIN   = (GPIO_CHIP, 17)    # GPIO3_C1
CS_PIN   = None               # HW CS via /dev/spidev3.0

SPI_BUS, SPI_DEV, SPI_MAX_HZ = 3, 0, 2_000_000
_CHUNK = 4096
_spi = None

# -------- detect gpiod major API --------
_GPIOD_V2 = hasattr(gpiod, "request_lines")

if _GPIOD_V2:
    # v2 puts direction/value enums under gpiod.line
    from gpiod.line import Direction as _Dir, Value as _Val

    def _set_out(pin, val):
        if pin is None: return
        chip, off = pin
        cfg = {off: gpiod.LineSettings(direction=_Dir.OUTPUT)}
        req = gpiod.request_lines(chip, consumer="epd", config=cfg)
        try:
            req.set_values({off: _Val.ACTIVE if val else _Val.INACTIVE})
        finally:
            if hasattr(req, "release"): req.release()
            elif hasattr(req, "close"): req.close()

    def _get_in(pin):
        if pin is None: return 0
        chip, off = pin
        cfg = {off: gpiod.LineSettings(direction=_Dir.INPUT)}
        req = gpiod.request_lines(chip, consumer="epd", config=cfg)
        try:
            vals = req.get_values([off])        # dict {off: Value} or list of Value
            v = vals[off] if isinstance(vals, dict) else vals[0]
            # Convert Value enum to int (ACTIVE=1, INACTIVE=0)
            if hasattr(v, "value"):
                return int(v.value)
            # Some builds may return bool already:
            return int(v)
        finally:
            if hasattr(req, "release"): req.release()
            elif hasattr(req, "close"): req.close()
else:
    # libgpiod v1 API (Debian python3-libgpiod)
    def _set_out(pin, val):
        if pin is None: return
        chip, off = pin
        with gpiod.Chip(chip) as c:
            line = c.get_line(off)
            line.request(consumer="epd", type=gpiod.LINE_REQ_DIR_OUT)
            line.set_value(1 if val else 0)
            line.release()

    def _get_in(pin):
        if pin is None: return 0
        chip, off = pin
        with gpiod.Chip(chip) as c:
            line = c.get_line(off)
            line.request(consumer="epd", type=gpiod.LINE_REQ_DIR_IN)
            v = line.get_value()
            line.release()
            return int(v)

# Waveshare driver hooks
def digital_write(pin, value): _set_out(pin, value)
def digital_read(pin):         return _get_in(pin)
def delay_ms(ms):              time.sleep(ms/1000)

def _to_list(d):
    if isinstance(d, (bytes, bytearray)): return list(d)
    if isinstance(d, list): return d
    return list(bytes(d))

def spi_writebyte(d):  _spi.xfer2(_to_list(d))
def spi_writebyte2(d):
    b=_to_list(d)
    for i in range(0, len(b), _CHUNK):
        _spi.xfer2(b[i:i+_CHUNK])

def module_init():
    global _spi
    _spi = spidev.SpiDev()
    _spi.open(SPI_BUS, SPI_DEV)
    _spi.max_speed_hz = SPI_MAX_HZ
    _spi.mode = 0
    return 0

def module_exit():
    try:
        if _spi: _spi.close()
    except: pass

# Optional attribute-style getters — some Waveshare modules expect these names
def RST_PIN_FUNC():  return RST_PIN
def DC_PIN_FUNC():   return DC_PIN
def BUSY_PIN_FUNC(): return BUSY_PIN
def CS_PIN_FUNC():   return CS_PIN
