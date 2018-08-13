# -*- encoding: utf-8 -*-

"""
Much to my frustration there is no Python RPC system that does *quite* 
what I want: small, secure (no arbitrary objects/code), 
supports binary data & no XML
"""

import io, struct, sys, decimal, socket, os, socketserver, logging

TUPLE_0=0
TUPLE_1=1
# and so on to
TUPLE_8=8
TUPLE_N=9
LIST_SHORT=10
LIST_MEDIUM=11
LIST_LONG=12
STR_SHORT=13
STR_MEDIUM=14
STR_LONG=15
BYTES_SHORT=16
BYTES_MEDIUM=17
BYTES_LONG=18
DICT_SHORT=19
DICT_MEDIUM=20
DICT_LONG=21
NONE=22
TRUE=23
FALSE=24
ZERO=25
INT_SHORT=26
INT_MEDIUM=27
INT_LONG=28
INT_LONGLONG=29
FLOAT=30
DECIMAL=31
EXCEPTION=32
STR_CONST=33

class RPCException(Exception):
    """
    Exceptions from the remote server
    All you get is the exception's string message, so backtrace/stack info
    This probably won't change, because security
    """
    pass


class Endpoint:
    """
    The base class for endpoints (client and server)
    """
    
    def __init__(self, wfile, rfile=None, constants=[]):
        """
        set up a connection
        wfile: file-like object for writing
        for convience, can also be an integer (in which case os.fdopen will be used) or a socket (in which case socket.makefile is used)
        rfile: file-like object for reading, defaults to same as wfile
        constants: a list (essentially a registry) of objects sent on the wire
        members can be 
        - strings: these will be compressed to one byte (who can still send arbitrary strings)
        - collections.namedtuple classes: these must be registered to use
        - other classes: must have a .load(contents) classmethod returning the object, and a .dump() instance method 
          returning the contents to be fed to .load
          (the load/dump representation must in turn be serialisable itself)
        there is a maximum size of the registry of 210 items
        """
        if type(wfile) is int:
            self.wfile = os.fdopen(wfile, "wb")
            if rfile is None:
                self.rfile = os.fdopen(wfile, "rb")
            else:
                self.rfile = os.fdopen(rfile, "rb")
        elif type(wfile) is socket.socket:
            self.wfile = wfile.makefile('wb')
            self.rfile = wfile.makefile('rb')
        elif rfile is None:
            self.wfile = self.rfile = wfile
        else:
            self.wfile = wfile
            self.rfile = rfile
        self.const = constants
        assert len(self.const) < 210, "too many constants"

    def close(self):
        """
        close the files for reading and writing
        (NOTE: depending on what they are, this may not close the underlying OS file descriptor)
        """
        self.rfile.close()
        self.wfile.close()

    def send(self, thing):
        """send thing on the wire
        thing must be
        - an int, float, str, bytes, or decimal.Decimal
        - a tuple, list or dictionary of the above.
        - an object if the class is registered at connection creation
        - a named tuple (again if registered)

        LIMITS: tuples and named tuples can't have more than 255 members
                decimals can't have more than 255 digits
                strings and bytes limited to 2^32 (i.e. 4G)
        """
        if type(thing) is tuple:
            logging.debug("sending tuple length {}".format(len(thing)))
            if len(thing) < 9:
                self.wfile.write(bytes([TUPLE_0+len(thing)]))
            else:
                assert len(thing) < 256, "tuple too long (> 256 members)"
                self.wfile.write(struct.pack("BB", TUPLE_N, len(thing)))
            for i in thing:
                self.send(i)
        elif type(thing) is list:
            self.write_flex(LIST_SHORT, len(thing))
            for i in thing:
                self.send(i)
        elif type(thing) is str:
            try:
                self.wfile.write(struct.pack("B", STR_CONST+self.const.index(thing)))
                logging.debug("sending string special")
            except ValueError:
                logging.debug("sending string {}".format(repr(thing)))
                thing = bytes(thing, 'utf-8', 'ignore')
                self.write_flex(STR_SHORT, len(thing))
                self.wfile.write(thing)
        elif type(thing) is bytes:
            self.write_flex(BYTES_SHORT, len(thing))
            self.wfile.write(thing)
        elif type(thing) is dict:
            self.write_flex(DICT_SHORT, len(thing))
            logging.debug("sending dict size {}".format(len(thing)))
            for k, v in thing.items():
                self.send(k)
                self.send(v)
        elif thing is None:
            logging.debug("sending None")
            self.wfile.write(struct.pack("B", NONE))
        elif thing is True:
            self.wfile.write(struct.pack("B", TRUE))
        elif thing is False:
            self.wfile.write(struct.pack("B", FALSE))
        elif thing == 0:
            self.wfile.write(struct.pack("B", ZERO))
        elif type(thing) is int:
            logging.debug("sending int {}".format(thing))
            if abs(thing) < 127:
                self.wfile.write(struct.pack("Bb", INT_SHORT, thing))
            elif abs(thing) < 2**15:
                self.wfile.write(struct.pack("!Bh", INT_MEDIUM, thing))
            elif abs(thing) < 2**31:  
                self.wfile.write(struct.pack("!Bl", INT_LONG, thing))
            else:
                self.wfile.write(struct.pack("!Bq", INT_LONGLONG, thing))
        elif type(thing) is float:
            self.wfile.write(struct.pack("!Bd", FLOAT, thing))
        elif type(thing) is decimal.Decimal:
            thing = bytes(str(thing),'ascii')
            assert len(thing) < 256, "decimal too big, > 256 chars"
            self.wfile.write(struct.pack("Bb", DECIMAL, len(thing)))
            self.wfile.write(thing)
        else:
            try:
                n = self.const.index(type(thing))
                self.wfile.write(struct.pack("B", STR_CONST+n))
                if isinstance(thing, tuple):
                    logging.debug("sending named tuple")
                    # its a named tuple: size is encoded in the named tuple type
                    for i in thing:
                        self.send(i)
                else:
                    d = thing.dump()
                    logging.debug("sending object .dump() = {}".format(repr(d)))
                    self.send(d)
            except ValueError:
                raise RPCException("unknown type {}".format(repr(thing)))


    def read_n(self, n):
        """read n bytes"""
        buf = b''
        while len(buf) < n:
            buf += self.rfile.read(n-len(buf))
        return buf

    def read(self, _format):
        """read and use struct.format"""
        return struct.unpack(_format, self.read_n(struct.calcsize(_format)))

    def read_flex(self, control, base):
        """read a 1/2/4 byte integer
        """
        if control == base: # a "_SHORT" variant
            n, = self.read('B')
        elif control == base+1: # "_MEDIUM" variant
            n, = self.read('!H')
        elif control == base+2: # "_LONG" variant
            n, = self.read("!I")
        else:
            raise RPCException("control number wrong {}".format(control))
        return n

    def write_flex(self, control, n):
        """write a 1/2/4 byte integer
        """
        if n < 256:
            self.wfile.write(struct.pack("BB", control, n))
        elif n < 2**16:
            self.wfile.write(struct.pack("!BH", control+1, n))
        elif n < 2**32:
            self.wfile.write(struct.pack("!BI", control+2, n))
        else:
            raise RPCException("integer too big {} for control code {}".format(n, control))
        
    def receive(self):
        """receive an arbitrary data structure on the wire
        """
        control, = self.read("B")
        if control >= TUPLE_0 and control < TUPLE_N:
            tuple_size = control-TUPLE_0
            logging.debug("receiving tuple size {}".format(tuple_size))
            t = tuple(self.receive() for _ in range(0, tuple_size))
            logging.debug("received tuple {}".format(repr(t)))
            return t
        elif control == TUPLE_N:
            tuple_size, = self.read("B")
            return tuple(self.receive() for _ in range(0, tuple_size))
        elif control in (LIST_SHORT, LIST_MEDIUM, LIST_LONG):
            n = self.read_flex(control, LIST_SHORT)
            return [self.receive() for _ in range(0, n)]
        elif control in (DICT_SHORT, DICT_MEDIUM, DICT_LONG):
            n = self.read_flex(control, DICT_SHORT)
            logging.debug("receiving dict size {}".format(n))
            d = dict([(self.receive(), self.receive()) for _ in range(0, n)])
            logging.debug("completed dict {}".format(repr(d)))
            return d
        elif control >= STR_CONST:
            c = self.const[control-STR_CONST]
            logging.debug("received control special {}".format(repr(c)))
            if type(c) is str:
                return c
            else:
                if issubclass(c, tuple):
                    # its a named tuple
                    logging.debug("receiving control special as named tuple")
                    t = tuple(self.receive() for _ in range(0, len(c._fields)))
                    return c (*t)
                else:
                    # well, it had better have a load() classmethod
                    x = self.receive()
                    logging.debug("received {} for feeding to .load()".format(repr(x)))
                    try:
                        y = c.load(x)
                    except BaseException as exc:
                        logging.debug("failure of load")
                        self.load_exc = exc
                        return None
                    else:
                        return y
        elif control in (STR_SHORT, STR_MEDIUM, STR_LONG):
            n = self.read_flex(control, STR_SHORT)
            s = self.read_n(n)
            s2 =  str(s, 'utf-8', 'replace')
            logging.debug("received string {}".format(repr(s2)))
            return s2
        elif control == EXCEPTION:
            n, = self.read("B")
            s = self.read_n(n)
            return RPCException(str(s, 'utf-8', 'replace'))
        elif control in (BYTES_SHORT, BYTES_MEDIUM, BYTES_LONG):
            n = self.read_flex(control, BYTES_SHORT)
            return self.read_n(n)
        elif control == NONE:
            return None
        elif control == TRUE:
            return True
        elif control == FALSE:
            return False
        elif control == ZERO:
            return 0
        else:
            direct_formats = {
                FLOAT:"!d",
                INT_SHORT:"b",
                INT_MEDIUM:"!h",
                INT_LONG:"!l",
                INT_LONGLONG:"!q"}
            if control in direct_formats:
                s = self.read(direct_formats[control])[0]
                logging.debug("received numeric {}".format(s))
                return s
            else:
                raise RPCException("unknown control code {}".format(control))
        
                
class Client(Endpoint):
    """
    a client connection
    "unknown" methods and their parameters are send to the server and the result returned
    parameters must be serialisable (see Endpoint.send)
    """

    def __getattr__(self, funcname):
        def method(*args, **kwargs):
            return self.call(funcname, args, kwargs)
        return method

    def call(self, funcname, args, kwargs):
        self.send((funcname, args, kwargs))
        self.wfile.flush()
        self.load_exc = None
        reply = self.receive()
        if self.load_exc:
            raise self.load_exc
        if isinstance(reply, RPCException):
            raise reply
        else:
            return reply

class Server(Endpoint):
    """
    A server object
    Unlike Client, to be useful it must be subclassed and the RPC calls you wish to expose are defined
    """

    def send_exception(self, exc):
        """send an exception object down the wire
        """
        s = bytes(str(exc)[:255], 'utf-8', 'replace')
        self.wfile.write(struct.pack("BB", EXCEPTION, len(s)))
        self.wfile.write(s)        
    
    def run(self):
        """
        keep serving method calls on a connection"""
        self.closed = False
        while not self.closed:
            self.load_exc = None
            command = self.receive()
            logging.debug("got command {}".format(repr(command)))
            if self.load_exc:
                self.send_exception(exc)
            else:
                try:
                    x = getattr(self, command[0]) (*command[1], **command[2])
                except BaseException as e:
                    self.send_exception(e)
                else:
                    logging.debug("sending reply {}".format(repr(x)))
                    self.send(x)
                    logging.debug("sent reply")
            logging.debug("flushing")
            self.wfile.flush()
            logging.debug("flushed")
        #Endpoint.close(self)

    def server_close(self):
        """set a flag for .run() to exit
        """
        self.closed = True

class Handler(socketserver.StreamRequestHandler, Server):
    """A server descendant for use to the socketserver apparatus from the standard library
    set a "const" attribute in the "master" server object object to provide a constants list to the
    handlers
    """

    def __init__(self, *args, **kwargs):
        socketserver.StreamRequestHandler.__init__(self, *args, **kwargs)
        
    def handle(self):
        logging.debug("handle() starts")
        self.const = getattr(self.server, 'const', [])
        self.run()
        logging.debug("handle() ends")
