# basicrpc
A basic binary RPC layer for Python

# Rationale

Much to my frustration there is no Python RPC system that does *quite* 
what I want: small, secure (no arbitrary objects/code), 
supports binary data & no XML.

This library does basic RPC using a custom binary protocol. It allows
arbitrary Python datastructures (tuples/lists/dictionaries)
that don't have to be pre-registered.

bytes objects are sent "raw" (i.e. no escaping or base 64 encoding required)

It tends to privilege bandwidth over CPU efficiency (but I'd be surprised if not faster
than XML and at least equal to JSON-RPC)

It can run over anything that can become a Python file-like object (TCP/IP, UNIX domain sockets,
pipes, FIFOs, etc).

# Security

Complex objects must be registered and have dump/load functions, no code over the wire
and no escaping required so there no way to "break out" of the wire protocol like SQL.

It's possible to consume server RAM by sending a lot of data, but you
must actually send the data (unlike XML where you can abuse circular references)

It doesn't provide encryption/authorisation: my advice is to fire up OpenSSH via Popen()
and use that.

# Example

```
sock = socket.socket(socket.AF_INET)
sock.connect(('127.0.0.1', 4242))
client = basicrpc.Client(sock, constants=CONSTS)
client.somefunction(2, 'a string')
client.close()
sock.close()
```

# Obtaining

It's on PIP

```
pip3 install basicrpc
```