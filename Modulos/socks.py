import socket
import ssl
import select
import threading
import os
import argparse
import logging
import resource

from abc import abstractproperty, ABCMeta, abstractmethod
from typing import List, Tuple, Union, Optional

resource.setrlimit(resource.RLIMIT_NOFILE, (65536, 65536))

logger = logging.getLogger(__name__)

WS_DEFAULT_RESPONSE = b'\r\n'.join(
    [
        b'HTTP/1.1 101',
        b'\r\n',
    ]
)

HTTP_DEFAULT_RESPONSE = b'\r\n'.join(
    [
        b'HTTP/1.1 200',
        b'\r\n',
    ]
)


class ResponseParser(metaclass=ABCMeta):
    @abstractmethod
    def parse(self, data: bytes) -> bytes:
        raise NotImplementedError


class ResponseParserAbstract(ResponseParser):
    def __init__(self, next: Union[ResponseParser, None] = None):
        self.next = next

    def parse(self, data: bytes) -> bytes:
        if self.next:
            return self.next.parse(data)
        return data


class WebsocketParseResponse(ResponseParserAbstract):
    __contains = (b'upgrade: websocket', b'upgrade: ws')

    def parse(self, data: bytes) -> bytes:
        for line in data.split(b'\r\n'):
            if line.lower() in self.__contains:
                return WS_DEFAULT_RESPONSE
        return super().parse(data)


class HttpParseResponse(ResponseParserAbstract):
    def parse(self, data: bytes) -> bytes:
        return HTTP_DEFAULT_RESPONSE


class ConnectionTypeParser:
    def __init__(self, type: bytes, address: Tuple[str, int]):
        self._type = type
        self._address = address

    @property
    def type(self) -> bytes:
        return self._type

    @property
    def address(self) -> Tuple[str, int]:
        return self._address

    @abstractproperty
    def name(self) -> str:
        raise NotImplementedError

    def is_valid(self, data: bytes) -> bool:
        return data.startswith(self._type)


class SSHConnectionType(ConnectionTypeParser):
    def __init__(self) -> None:
        super().__init__(b'SSH-', ('0.0.0.0', 22))

    @property
    def name(self) -> str:
        return 'SSH'



class Connection:
    def __init__(self, conn: Union[socket.socket, ssl.SSLSocket], addr: Tuple[str, int]):
        self.__conn = conn
        self.__addr = addr
        self.__buffer = b''
        self.__closed = False

    @property
    def conn(self) -> Union[socket.socket, ssl.SSLSocket]:
        if not isinstance(self.__conn, (socket.socket, ssl.SSLSocket)):
            raise TypeError('Connection is not a socket')

        if not self.__conn.fileno() > 0:
            raise ConnectionError('Connection is closed')

        return self.__conn

    @conn.setter
    def conn(self, conn: Union[socket.socket, ssl.SSLSocket]):
        if not isinstance(conn, (socket.socket, ssl.SSLSocket)):
            raise TypeError('Connection is not a socket')

        if not conn.fileno() > 0:
            raise ConnectionError('Connection is closed')

        self.__conn = conn

    @property
    def addr(self) -> Tuple[str, int]:
        return self.__addr

    @addr.setter
    def addr(self, addr: Tuple[str, int]):
        self.__addr = addr

    @property
    def buffer(self) -> bytes:
        return self.__buffer

    @buffer.setter
    def buffer(self, data: bytes) -> None:
        self.__buffer = data

    @property
    def closed(self) -> bool:
        return self.__closed

    @closed.setter
    def closed(self, value: bool) -> None:
        self.__closed = value

    def close(self):
        self.conn.close()
        self.closed = True

    def read(self, size: int = 4096) -> Optional[bytes]:
        data = self.conn.recv(size)
        return data if len(data) > 0 else None

    def write(self, data: Union[bytes, str]) -> int:
        if isinstance(data, str):
            data = data.encode()

        if len(data) <= 0:
            raise ValueError('Write data is empty')

        return self.conn.send(data)

    def queue(self, data: Union[bytes, str]) -> int:
        if isinstance(data, str):
            data = data.encode()

        if len(data) <= 0:
            raise ValueError('Queue data is empty')

        self.__buffer += data
        return len(data)

    def flush(self) -> int:
        sent = self.write(self.__buffer)
        self.__buffer = self.__buffer[sent:]
        return sent


class Client(Connection):
    def __str__(self):
        return 'Cliente - %s:%s' % self.addr


class Server(Connection):
    def __str__(self):
        return 'Servidor - %s:%s' % self.addr

    @classmethod
    def of(cls, addr: Tuple[str, int]) -> 'Server':
        return cls(socket.socket(socket.AF_INET, socket.SOCK_STREAM), addr)

    def connect(self, addr: Tuple[str, int] = None, timeout: int = 5) -> None:
        self.addr = addr or self.addr
        self.conn = socket.create_connection(self.addr, timeout)
        self.conn.settimeout(None)

        logger.debug('%s Conexão estabelecida' % self)


class Proxy(threading.Thread):
    def __init__(self, client: Client, server: Optional[Server] = None) -> None:
        super().__init__()
        self.client = client
        self.server = server
        self.__running = False
        self.__http_response_parser = WebsocketParseResponse(HttpParseResponse())

    @property
    def running(self) -> bool:
        if self.server and self.server.closed and self.client.closed:
            self.__running = False
        return self.__running

    @running.setter
    def running(self, value: bool) -> None:
        self.__running = value

    def _process_request(self, data: bytes) -> None:
        if self.server and not self.server.closed:
            self.server.queue(data)
            return

        connection_type = SSHConnectionType()

        if connection_type.is_valid(data):
            if connection_type:
                logger.info(
                    '%s -> Modo %s - %s:%s',
                    self.client,
                    connection_type.name,
                    *connection_type.address,
                )
                self.server = Server.of(connection_type.address)
                self.server.connect()
                self.server.queue(data)
                return

        logger.info(
            '%s -> Solicitação: %s',
            self.client,
            data,
        )
        self.client.queue(self.__http_response_parser.parse(data))

    def _get_waitable_lists(self) -> Tuple[List[socket.socket]]:
        r, w, e = ([self.client.conn], [], [])  # type: ignore

        if self.server and not self.server.closed:
            r.append(self.server.conn)

        if self.client.buffer:
            w.append(self.client.conn)

        if self.server and not self.server.closed and self.server.buffer:
            w.append(self.server.conn)

        return r, w, e  # type: ignore

    def _process_wlist(self, wlist: List[socket.socket]) -> None:
        if self.client.conn in wlist:
            sent = self.client.flush()
            logger.debug('%s -> enviado %s bytes' % (self.client, sent))

        if self.server and not self.server.closed and self.server.conn in wlist:
            sent = self.server.flush()
            logger.debug('%s -> enviado %s bytes' % (self.server, sent))

    def _process_rlist(self, rlist: List[socket.socket]) -> None:
        if self.client.conn in rlist:
            data = self.client.read(8192)
            self.running = data is not None
            if data and self.running:
                self._process_request(data)
                logger.debug('%s -> recebido %s bytes' % (self.client, len(data)))

        if self.server and not self.server.closed and self.server.conn in rlist:
            data = self.server.read(8192)
            self.running = data is not None
            if data and self.running:
                self.client.queue(data)
                logger.debug('%s -> recebido %s bytes' % (self.server, len(data)))

    def _process(self) -> None:
        self.running = True

        while self.running:
            rlist, wlist, xlist = self._get_waitable_lists()  # type: ignore
            r, w, _ = select.select(rlist, wlist, xlist, 1)  # type: ignore

            self._process_wlist(w)
            self._process_rlist(r)

    def run(self) -> None:
        try:
            logger.info('%s conectado' % self.client)
            self._process()
        except Exception as e:
            logger.exception('%s Erro: %s' % (self.client, e))
        finally:
            self.client.close()
            if self.server and not self.server.closed:
                self.server.close()

            logger.info('%s desconectado' % self.client)


class TCP:
    def __init__(self, addr: Tuple[str, int], backlog: int = 5):
        self.__addr = addr
        self.__backlog = backlog

        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def __str__(self) -> str:
        return '%s - %s:%d' % (self.__class__.__name__, *self.__addr)

    def handle(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        raise NotImplementedError()

    def run(self) -> None:
        self.__sock.bind(self.__addr)
        self.__sock.listen(self.__backlog)

        logger.info('Servidor %s iniciado' % self)

        try:
            while True:
                conn, addr = self.__sock.accept()
                self.handle(conn, addr)
        except KeyboardInterrupt:
            pass
        finally:
            logger.info('Finalizando servidor...')
            self.__sock.close()


class HTTP(TCP):
    def handle(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        client = Client(conn, addr)
        proxy = Proxy(client)
        proxy.daemon = True
        proxy.start()

def main():
    server = HTTP(("0.0.0.0", "8080"), args.backlog)
    logging.basicConfig(
        level=getattr(logging, args.log.upper()),
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )
    server.run()

if __name__ == '__main__':
    main()
