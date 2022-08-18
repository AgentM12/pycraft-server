
def parse_time(time_str, def_unit='s'):
    '''
    Parses a simple time to seconds (rounded down), from minutes or hours as a float.
    '''
    n = len(time_str) - 1

    if time_str[n:] in '0123456789': n += 1 # Ensure a time-unit is never a number.

    t = time_str[:n]
    unit = time_str[n:]

    if (unit == 't' or (unit == '' and def_unit == 't')): return float(t) / 20
    if (unit == 's' or (unit == '' and def_unit == 's')): return int(t)
    if (unit == 'm' or (unit == '' and def_unit == 'm')): return int(float(t) * 60)
    if (unit == 'h' or (unit == '' and def_unit == 'h')): return int(float(t) * 3600)
    if (unit == 'd' or (unit == '' and def_unit == 'd')): return int(float(t) * 86400)
    raise Exception('Did not recognize unit: %s' % unit)

def max_cmd_len(command, cap, f=None):
    '''
    Returns True if the length of the command exceeds the cap.
    Uses f to print.
    '''
    if len(command) > cap:
        if not (f is None):
            f('Found trailing data: "%s"' % ' '.join(command[cap:]), 3)
        return True
    return False

def next_cmd(args):
    '''
    Splits list into head and tail.
    '''
    if (len(args) > 0):
        a, *b = args
        return (a, b)
    return (None, [])