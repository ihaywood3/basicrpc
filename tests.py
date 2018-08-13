import unittest, socket, socketserver, sys
from collections import namedtuple

testtuple = namedtuple("testtuple","foo bar")

import binaryrpc

class TestHandler(binaryrpc.Handler):

    def mul(self, a, b):
        return a*b

    def add(self, a, b):
        return a+b

    def update(self, a, b):
        a.update(b)
        a['surprise'] = 'twenty'
        return a

    def object(self, n):
        n.swap()
        return n

    def repr(self, r):
        return repr(r)

class TestClass:

    @classmethod
    def load(kls, contents):
        return kls (contents)

    def __init__(self, contents):
        self.field1, self.field2 = contents

    def dump(self):
        return (self.field1, self.field2)

    def swap(self):
        n = self.field1
        self.field1 = self.field2
        self.field2 = n
    
CONSTS=['foo', 'baz', TestClass, testtuple]

class TestRPC(unittest.TestCase):

    def setUp(self):
        #r1, w1 = os.pipe()
        #r2, w2 = os.pipe()
        #self.client = Client(w1, r2)
        #self.server = TestServer(w2, r1)
        #if os.fork() == 0:
        #    self.server.run()
        self.sock = socket.socket(socket.AF_INET)
        self.sock.connect(('127.0.0.1',4242))
        self.client = binaryrpc.Client(self.sock, constants=CONSTS)

    def tearDown(self):
        self.client.server_close()
        self.client.close()
        self.sock.close()
        
    def test_add(self):
        self.assertEqual(self.client.add(1,2), 3)

    def test_mul(self):
        self.assertEqual(self.client.mul(2, 3), 6)

    def test_list(self):
        self.assertEqual(self.client.add([1,2],[3,4]), [1,2,3,4])

    def test_dict(self):
        a = {'foo': 3, 'bar':(7, 4.3), 'baz': 35364634, 'bur': 2**35+42}
        b = self.client.update(a, {3: "ℵℶℷ"})
        self.assertTrue(3 in b)
        self.assertEqual(b[3], "ℵℶℷ")
        self.assertEqual(len(b), 6)

    def test_object(self):
        t = TestClass(('foo', 'bar'))
        t = self.client.object(t)
        self.assertEqual(t.dump(), ('bar', 'foo'))

    def test_namedtuple(self):
        self.assertTrue(self.client.repr(testtuple(1, 2)), "testtuple(foo=1, bar=2)")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'server':
        server = socketserver.TCPServer(('127.0.0.1', 4242), TestHandler)
        server.const = CONSTS
        server.serve_forever()
    else:
        unittest.main()
