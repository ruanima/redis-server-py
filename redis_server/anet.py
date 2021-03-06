import os
import sys
import socket
from typing import NewType, Tuple, Optional as Opt, Union
from .csix import *
from .util import SocketCache

Address = Tuple[str, int]

class AnetErr(Exception):
    pass

ANET_OK = 0
ANET_ERR = -1
ANET_ERR_LEN = 256

# /* Flags used with certain functions. */
ANET_NONE = 0
ANET_IP_ONLY = (1<<0)

# // 通用连接创建函数，被其他高层函数所调用
ANET_CONNECT_NONE = 0
ANET_CONNECT_NONBLOCK = 1

# 设置地址可重用
def anetSetReuseAddr(fd: socket.socket) -> None:
    try:
        fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError:
        fd.close()
        raise

def anetNonBlock(fd: socket.socket) -> None:
    try:
        fd.setblocking(False)
    except OSError:
        fd.close()
        raise

def anetSetTcpNoDelay(fd: socket.socket, val: int) -> None:
    fd.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, val)

def anetTcpKeepAlive(fd: socket.socket) -> None:
    fd.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

def anetTcpGenericConnect(addr: str, port: int, source_addr: Opt[str], flags: int) -> socket.socket:
    servinfo = socket.getaddrinfo(addr, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    s = None
    bound = 0
    # (family, type, proto, canonname, sockaddr)
    for sinfo in servinfo:
        try:
            s = socket.socket(sinfo[0], sinfo[1], sinfo[2])
        except OSError:
            continue
        anetSetReuseAddr(s)
        SocketCache.set(s)
        if flags & ANET_CONNECT_NONBLOCK:
            anetNonBlock(s)
        if source_addr:
            try:
                bservinfo = socket.getaddrinfo(source_addr, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            except OSError:
                return s
            for info in bservinfo:
                try:
                    s.bind(info[4])
                    bound = 1
                    break
                except OSError:
                    continue
            if not bound:
                raise AnetErr('bind error')

        s.connect((addr, port))
        return s
    if not s:
        raise AnetErr('create socket fail')
    return s

def anetTcpConnect(addr: str, port: int) -> socket.socket:
    return anetTcpGenericConnect(addr, port, None, ANET_CONNECT_NONE)

def anetTcpNonBlockConnect(addr: str, port: int) -> socket.socket:
    return anetTcpGenericConnect(addr, port, None, ANET_CONNECT_NONBLOCK)

def anetTcpNonBlockBindConnect(addr: str, port: int, source_addr: str) -> socket.socket:
    return anetTcpGenericConnect(addr, port, source_addr, ANET_CONNECT_NONBLOCK)

def anetUnixGenericConnect(path: str, flags: int) -> socket.socket:
    s = socket.socket(socket.AF_UNIX)
    if flags & ANET_CONNECT_NONBLOCK:
        anetNonBlock(s)
    s.connect(path)
    SocketCache.set(s)
    return s

def anetUnixConnect(path: str, flags: int) -> socket.socket:
    return anetUnixGenericConnect(path, ANET_CONNECT_NONE)

def anetUnixNonBlockConnect(path: str, flags: int) -> socket.socket:
    return anetUnixGenericConnect(path, ANET_CONNECT_NONBLOCK)

def anetRead(fd: socket.socket, count: int) -> bytearray:
    buf = bytearray(count)
    view = memoryview(buf)
    while count:
        nbytes = fd.recv_into(view, count)
        view = view[nbytes:]   # slicing views is cheap
        count -= nbytes
    return buf

def anetGenericResolve(host: str, flags: int) -> str:
    if flags & ANET_IP_ONLY:
        ai_flags = int(socket.AI_NUMERICHOST)
    else:
        ai_flags = 0
    info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM, ai_flags)
    # (family, type, proto, canonname, sockaddr)
    return info[0][4][0]

def anetResolve(host: str) -> str:
    return anetGenericResolve(host, ANET_NONE)

def anetResolveIP(host: str) -> str:
    return anetGenericResolve(host, ANET_IP_ONLY)

def anetV6Only(s: socket.socket) -> None:
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.IPPROTO_IPV6, 1)
    except OSError:
        s.close()
        raise

def anetListen(s: socket.socket, host: str, port: Opt[int], backlog: int) -> None:
    try:
        s.bind((host, port))
        s.listen(backlog)
    except OSError:
        s.close()
        raise

def _anetTcpServer(port: int, bindaddr: Opt[str], af: int, backlog: int) -> socket.socket:
    serverinfo = socket.getaddrinfo(bindaddr, port, af, socket.SOCK_STREAM, flags=socket.AI_PASSIVE)
    s = None
    for (family, type_, proto, _, sockaddr) in serverinfo:
        try:
            s = socket.socket(family, type_, proto)
        except OSError:
            continue
        if af == socket.AF_INET6:
            anetV6Only(s)
        anetSetReuseAddr(s)
        anetListen(s, sockaddr[0], sockaddr[1], backlog)
        SocketCache.set(s)
    if not s:
        raise AnetErr('start tcp server fail')
    return s

def anetTcpServer(port: int, bindaddr: Opt[str], backlog: int) -> socket.socket:
    return _anetTcpServer(port, bindaddr, socket.AF_INET, backlog)

def anetTcp6Server(port: int, bindaddr: Opt[str], backlog: int) -> socket.socket:
    return _anetTcpServer(port, bindaddr, socket.AF_INET6, backlog)

def anetCreateSocket(domain: int) -> socket.socket:
    try:
        s = socket.socket(domain, socket.SOCK_STREAM)
        anetSetReuseAddr(s)
        SocketCache.set(s)
        return s
    except OSError:
        s.close()
        raise

def anetUnixServer(path: str, perm: int, backlog: int) -> socket.socket:
    s = anetCreateSocket(socket.AF_UNIX)
    anetListen(s, path, None, backlog)
    if perm:
        os.chmod(path, perm)
    return s

def anetTcpAccept(serversock: socket.socket) -> Tuple[socket.socket, Address]:
    sock, addr = serversock.accept()
    SocketCache.set(sock)
    return sock, addr

def anetUnixAccept(serversock: socket.socket) -> Tuple[socket.socket, str]:
    sock, addr = serversock.accept()
    SocketCache.set(sock)
    return sock, addr

def anetWrite(fd: socket.socket, buf: cstr) -> None:
    return fd.sendall(buf)

def anetEnableTcpNoDelay(fd: socket.socket) -> None:
    return anetSetTcpNoDelay(fd, 1)

def anetDisableTcpNoDelay(fd: socket.socket) -> None:
    return anetSetTcpNoDelay(fd, 0)

def anetPeerToString(fd: socket.socket) -> Address:
    return fd.getpeername()

def anetKeepAlive(fd: socket.socket, interval: int) -> None:
    if sys.platform != 'linux':
        fd.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        return

    fd.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, interval)
    fd.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, interval // 3 or 1)
    fd.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 3)

def anetSockName(fd: socket.socket) -> Address:
    return fd.getsockname()
