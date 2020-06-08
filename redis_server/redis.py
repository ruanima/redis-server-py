import locale
import random
import time
import logging
import os
from typing import List, Callable, Optional as Opt, Tuple
from dataclasses import dataclass
from .csix import timeval
from .ae import aeEventLoop, aeSetBeforeSleepProc, aeMain, aeDeleteEventLoop
from .config import ServerConfig as Conf

__version__ = '0.0.1'

logger = logging.getLogger(__name__)

class RedisClient(object):
    pass

class redisCommand(object):
    pass

class clientBufferLimitsConfig:
    def __init__(self):
        # 硬限制
        self.hard_limit_bytes: int = 0
        # 软限制
        self.soft_limit_bytes: int = 0
        # 软限制时限
        self.soft_limit_seconds: int = 0

class redisOpArray:
    # TODO(ruan.lj@foxmail.com): something to do.
    pass

@dataclass
class saveparam:
    # 多少秒之内
    seconds: int = 0
    # 发生多少次修改
    changes: int = 0

class RedisServer(object):
    def __init__(self):
        self.configfile:str = ''  # 配置文件的绝对路径
        self.hz:int = 0      # serverCron() 每秒调用的次数
        self.db: List['RedisDB'] = []
        self.commands: dict = {}   # 命令表（受到 rename 配置选项的作用）
        self.orig_commands: dict = {}   # 命令表（无 rename 配置选项的作用）
        self.el: aeEventLoop = None   # 事件状态
        self.lruclock: int = 0   # /* Clock for LRU eviction */
        # 关闭服务器的标识
        self.shutdown_asap: int = 0      # /* SHUTDOWN needed ASAP */
        # 在执行 serverCron() 时进行渐进式 rehash
        self.activerehashing: int =0     # /* Incremental rehash in serverCron() */
        self.requirepass: str = ''        # /* Pass for AUTH command, or NULL */
        self.pidfile: str = ''            # /* PID file path */
        self.arch_bits: int = 0            # /* 32 or 64 depending on sizeof(long) */
        # serverCron() 函数的运行次数计数器
        self.cronloops: int = 0            # /* Number of times the cron function run */
        # 本服务器的 RUN ID
        self.runid: str = ''    # /* ID always different at every exec. */
        # 服务器是否运行在 SENTINEL 模式
        self.sentinel_mode: int = 0
        # /* Networking */
        # TCP 监听端口
        self.port: int = 0                       # /* TCP listening port */
        self.tcp_backlog: int = 0                # /* TCP listen() backlog */
        # 地址
        self.bindaddr: str = ''     # /* Addresses we should bind to */
        # 地址数量
        self.bindaddr_count: int = 0             # /* Number of addresses in server.bindaddr[] */
        # UNIX 套接字
        self.unixsocket: str = ''               # /* UNIX socket path */
        self.unixsocketperm: str = ''          # /* UNIX socket permission */
        # 描述符
        self.ipfd: List[int] = []    # /* TCP socket file descriptors */
        # 描述符数量
        self.ipfd_count: int = 0                 # /* Used slots in ipfd[] */
        # UNIX 套接字文件描述符
        self.sofd: int = 0                       # /* Unix socket file descriptor */
        self.cfd: List[int] = []    # /* Cluster bus listening socket */
        self.cfd_count = 0                  # /* Used slots in cfd[] */
        # 一个链表，保存了所有客户端状态结构
        self.clients: list = []                  # /* List of active clients */
        # 链表，保存了所有待关闭的客户端
        self.clients_to_close: list = []         # /* Clients to close asynchronously */
        # 链表，保存了所有从服务器，以及所有监视器
        self.slaves: list = []
        self.monitors: list = []        # /* List of slaves and MONITORs */
        # 服务器的当前客户端，仅用于崩溃报告
        self.current_client: RedisClient = None    # /* Current client, only used on crash report */
        self.clients_paused: int = 0             # /* True if clients are currently paused */
        self.clients_pause_end_time: int = 0    # /* Time when we undo clients_paused */
        # 网络错误
        self.neterr: str = ''    # /* Error buffer for anet.c */
        # MIGRATE 缓存
        self.migrate_cached_sockets: dict = {}   # /* MIGRATE cached sockets */

        self.daemonize: int = 0   # /* True if running as a daemon */
        self.cluster_enabled: int = 0
        self.port: int = 0
        self.ipfd_count: int = 0
        self.sofd: int = 0
        self.unixsocket: str = ""
        #  RDB / AOF loading information
        #  We are loading data from disk if true
        self.loading: int = 0
        # 正在载入的数据的大小
        self.loading_total_bytes: int = 0
        # 已载入数据的大小
        self.loading_loaded_bytes: int = 0
        # 开始进行载入的时间
        self.loading_start_time: int = 0
        self.loading_process_events_interval_bytes: int = 0
        # 常用命令的快捷连接
        self.delCommand: redisCommand = None
        self.multiCommand: redisCommand = None
        self.lpushCommand: redisCommand = None
        self.lpopCommand: redisCommand = None
        self.rpopCommand: redisCommand = None

        #  Fields used only for stats
        #  服务器启动时间
        #  Server start time
        self.stat_starttime: int = 0
        # 已处理命令的数量
        #  Number of processed commands
        self.stat_numcommands: int = 0
        # 服务器接到的连接请求数量
        #  Number of connections received
        self.stat_numconnections: int = 0
        # 已过期的键数量
        #  Number of expired keys
        self.stat_expiredkeys: int = 0
        # 因为回收内存而被释放的过期键的数量
        #  Number of evicted keys (maxmemory)
        self.stat_evictedkeys: int = 0
        # 成功查找键的次数
        #  Number of successful lookups of keys
        self.stat_keyspace_hits: int = 0
        # 查找键失败的次数
        #  Number of failed lookups of keys
        self.stat_keyspace_misses: int = 0
        # 已使用内存峰值
        #  Max used memory record
        self.stat_peak_memory: int = 0
        # 最后一次执行 fork() 时消耗的时间
        #  Time needed to perform latest fork()
        self.stat_fork_time: int = 0
        # 服务器因为客户端数量过多而拒绝客户端连接的次数
        #  Clients rejected because of maxclients
        self.stat_rejected_conn: int = 0
        # 执行 full sync 的次数
        #  Number of full resyncs with slaves.
        self.stat_sync_full: int = 0
        # PSYNC 成功执行的次数
        #  Number of accepted PSYNC requests.
        self.stat_sync_partial_ok: int = 0
        # PSYNC 执行失败的次数
        #  Number of unaccepted PSYNC requests.
        self.stat_sync_partial_err: int = 0

        #  slowlog
        # 保存了所有慢查询日志的链表
        #  SLOWLOG list of commands
        self.slowlog = None
        # 下一条慢查询日志的 ID
        #  SLOWLOG current entry ID
        self.slowlog_entry_id: int = 0
        # 服务器配置 slowlog-log-slower-than 选项的值
        #  SLOWLOG time limit (to get logged)
        self.slowlog_log_slower_than: int = 0
        # 服务器配置 slowlog-max-len 选项的值
        #  SLOWLOG max number of items logged
        self.slowlog_max_len = 0
        #  RSS sampled in serverCron().
        self.resident_set_size = 0
        #  The following two are used to track instantaneous "load" in terms* of operations per second.
        # 最后一次进行抽样的时间
        #  Timestamp of last sample (in ms)
        self.ops_sec_last_sample_time: int = 0
        # 最后一次抽样时，服务器已执行命令的数量
        #  numcommands in last sample
        self.ops_sec_last_sample_ops: int = 0
        # 抽样结果
        self.ops_sec_samples: List[int] = []
        # 数组索引，用于保存抽样结果，并在需要时回绕到 0
        self.ops_sec_idx = 0

        #  Configuration
        # 日志可见性
        #  Loglevel in redis.conf
        self.verbosity: int = 0
        # 客户端最大空转时间
        #  Client timeout in seconds
        self.maxidletime: int = 0
        # 是否开启 SO_KEEPALIVE 选项
        #  Set SO_KEEPALIVE if non-zero.
        self.tcpkeepalive: int = 0
        #  Can be disabled for testing purposes.
        self.active_expire_enabled: int = 0
        #  Limit for client query buffer length
        self.client_max_querybuf_len: int = 0
        #  Total number of configured DBs
        self.dbnum: int = 0
        #  True if running as a daemon
        self.daemonize: int = 0
        # 客户端输出缓冲区大小限制
        # 数组的元素有 REDIS_CLIENT_LIMIT_NUM_CLASSES 个
        # 每个代表一类客户端：普通、从服务器、pubsub，诸如此类
        self.client_obuf_limits: List[clientBufferLimitsConfig] = []

        #  AOF persistence
        # AOF 状态（开启/关闭/可写）
        #  REDIS_AOF_(ON|OFF|WAIT_REWRITE)
        self.aof_state: int = 0
        # 所使用的 fsync 策略（每个写入/每秒/从不）
        #  Kind of fsync() policy
        self.aof_fsync: int = 0
        #  Name of the AOF file
        self.aof_filename: str = 0
        #  Don't fsync if a rewrite is in prog.
        self.aof_no_fsync_on_rewrite: int = 0
        #  Rewrite AOF if % growth is > M and...
        self.aof_rewrite_perc: int = 0
        #  the AOF file is at least N bytes.
        self.aof_rewrite_min_size: int = 0
        # 最后一次执行 BGREWRITEAOF 时， AOF 文件的大小
        #  AOF size on latest startup or rewrite.
        self.aof_rewrite_base_size: int = 0
        # AOF 文件的当前字节大小
        #  AOF current size.
        self.aof_current_size: int = 0
        #  Rewrite once BGSAVE terminates.
        self.aof_rewrite_scheduled: int = 0
        # 负责进行 AOF 重写的子进程 ID
        #  PID if rewriting process
        self.aof_child_pid: int = 0
        # AOF 重写缓存链表，链接着多个缓存块
        #  Hold changes during an AOF rewrite.
        self.aof_rewrite_buf_blocks = None   # NOTE: redis list ?
        # AOF 缓冲区
        #  AOF buffer, written before entering the event loop
        self.aof_buf = None   # TODO(ruan.lj@foxmail.com): sds or bytearry.
        # AOF 文件的描述符
        #  File descriptor of currently selected AOF file
        self.aof_fd: int = 0
        # AOF 的当前目标数据库
        #  Currently selected DB in AOF
        self.aof_selected_db: int = 0
        # 推迟 write 操作的时间
        #  UNIX time of postponed AOF flush
        self.aof_flush_postponed_start = 0
        # 最后一直执行 fsync 的时间
        #  UNIX time of last fsync()
        self.aof_last_fsync = 0
        #  Time used by last AOF rewrite run.
        self.aof_rewrite_time_last = 0
        # AOF 重写的开始时间
        #  Current AOF rewrite start time.
        self.aof_rewrite_time_start = 0
        # 最后一次执行 BGREWRITEAOF 的结果
        #  REDIS_OK or REDIS_ERR
        self.aof_lastbgrewrite_status: int = 0
        # 记录 AOF 的 write 操作被推迟了多少次
        #  delayed AOF fsync() counter
        self.aof_delayed_fsync: int = 0
        # 指示是否需要每写入一定量的数据，就主动执行一次 fsync()
        #  fsync incrementally while rewriting?
        self.aof_rewrite_incremental_fsync: int = 0
        #  REDIS_OK or REDIS_ERR
        self.aof_last_write_status: int = 0
        #  Valid if aof_last_write_status is ERR
        self.aof_last_write_errno: int = 0

        #  RDB persistence
        # 自从上次 SAVE 执行以来，数据库被修改的次数
        #  Changes to DB from the last save
        self.dirty: int = 0
        # BGSAVE 执行前的数据库被修改次数
        #  Used to restore dirty on failed BGSAVE
        self.dirty_before_bgsave: int = 0
        # 负责执行 BGSAVE 的子进程的 ID
        # 没在执行 BGSAVE 时，设为 -1
        #  PID of RDB saving child
        self.rdb_child_pid: int = 0
        #  Save points array for RDB
        self.saveparams: List[saveparam] = []
        #  Number of saving points
        self.saveparamslen: int = 0
        #  Name of RDB file
        self.rdb_filename: str = ''
        #  Use compression in RDB?
        self.rdb_compression: int = 0
        #  Use RDB checksum?
        self.rdb_checksum: int = 0
        # 最后一次完成 SAVE 的时间
        #  Unix time of last successful save
        self.lastsave = 0
        # 最后一次尝试执行 BGSAVE 的时间
        #  Unix time of last attempted bgsave
        self.lastbgsave_try = 0
        # 最近一次 BGSAVE 执行耗费的时间
        #  Time used by last RDB save run.
        self.rdb_save_time_last = 0
        # 数据库最近一次开始执行 BGSAVE 的时间
        #  Current RDB save start time.
        self.rdb_save_time_start = 0
        # 最后一次执行 SAVE 的状态
        #  REDIS_OK or REDIS_ERR
        self.lastbgsave_status: int = 0
        #  Don't allow writes if can't BGSAVE
        self.stop_writes_on_bgsave_err: int = 0

        #  Propagation of commands in AOF / replication
        #  Additional command to propagate.
        self.also_propagate: redisOpArray = None

        #  Blocked clients
        #  Number of clients blocked by lists
        self.bpop_blocked_clients: int = 0
        #  list of clients to unblock before next loop
        self.unblocked_clients: List = []
        #  List of readyList structures for BLPOP & co
        self.ready_keys: List = []
        #  Sort parameters - qsort_r() is only available under BSD so we* have to take this state global, in order to pass it to sortCompare()
        self.sort_desc: int = 0
        self.sort_alpha: int = 0
        self.sort_bypattern: int = 0
        self.sort_store: int = 0
        #  Zip structure config, see redis.conf for more information
        self.hash_max_ziplist_entries: int = 0
        self.hash_max_ziplist_value: int = 0
        self.list_max_ziplist_entries: int = 0
        self.list_max_ziplist_value: int = 0
        self.set_max_intset_entries: int = 0
        self.zset_max_ziplist_entries: int = 0
        self.zset_max_ziplist_value: int = 0
        self.hll_sparse_max_bytes: int = 0
        #  Unix time sampled every cron cycle.
        self.unixtime: int = 0
        #  Like 'unixtime' but with milliseconds resolution.
        self.mstime: int = 0

        #  Pubsub
        # 字典，键为频道，值为链表
        # 链表中保存了所有订阅某个频道的客户端
        # 新客户端总是被添加到链表的表尾
        #  Map channels to list of subscribed clients
        self.pubsub_channels: dict = {}
        # 这个链表记录了客户端订阅的所有模式的名字
        #  A list of pubsub_patterns
        self.pubsub_patterns: List = []
        self.notify_keyspace_events: int = 0
        #  Events to propagate via Pub/Sub. This is anxor of REDIS_NOTIFY... flags.
        #  Cluster
        #  Is cluster enabled?  NOTE: not support cluster mode
        self.cluster_enabled: int = 0
        #  Assert & bug reporting
        self.assert_failed: str = ''
        self.assert_file: str = ''
        self.assert_line: int = 0
        #  True if bug report header was already logged.
        self.bug_report_start: int = 0
        #  Software watchdog period in ms. 0 = off
        self.watchdog_period: int = 0

server = RedisServer()

def checkForSentinelMode() -> int:
    import sys
    if 'redis-sentinel' in sys.argv[0]:
        return 1
    if '--sentinel' in sys.argv[1:]:
        return 1
    return 0

def initServerConfig():
    # TODO(ruan.lj@foxmail.com): something to do.
    pass

def initServer():
    # TODO(ruan.lj@foxmail.com): something to do.
    pass

def initSentinelConfig():
    # TODO(ruan.lj@foxmail.com): something to do.
    pass

def initSentinel():
    # TODO(ruan.lj@foxmail.com): something to do.
    pass

def loadServerConfig(filename:str, options: dict) -> None:
    from collections import OrderedDict
    config = OrderedDict()
    if filename:
        with open(filename) as fp:
            for line in fp:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                parts = line.rsplit("#")[0].split(maxsplit=1)
                if len(parts) != 2:
                    print('wrong config line {!r}'.format(line))
                    continue
                key, val = parts
                config[key.lower()] = val.strip('"')
    for key, val in options.items():
        config[key] = val
    print(config)
    # TODO(ruan.lj@foxmail.com): set configs to server.

def parse_server_args() -> Tuple[str, dict]:
    def handle_version(args):
        print('Redis server v={}'.format(__version__))

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', help='show version info and exit', action='store_true')
    parser.add_argument('conf', help='config file path', nargs='?')
    parsed, unknown = parser.parse_known_args()
    options = {}
    for arg in unknown:
        if arg.startswith(("-", "--")):
            tmp = arg.split('=')[0]
            parser.add_argument(tmp)
            options[tmp.strip('-')] = ''
    args = parser.parse_args()

    if args.version:
        handle_version(args)
        exit()

    for key in options:
        options[key] = getattr(args, key, '')
    loadServerConfig(args.conf, options)
    if args.conf:
        server.configfile = os.path.abspath(args.conf)
    if not (args.conf or options):
        print("Warning: no config file specified, using the default config")
    return args.conf, options

def daemonize():
    if os.fork() != 0:
        exit()
    os.setsid()
    fd = os.open('/dev/null', os.O_RDWR, 0)
    os.dup2(fd, 0)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    if fd > 2:
        os.close(fd)

def redisAsciiArt() -> None:
    art = (
        "                _._ \n"
        "           _.-``__ ''-._ \n"
        "      _.-``    `.  `_.  ''-._           Redis {ver} (00000000/0) 64 bit \n"
        "  .-`` .-```.  ```\/    _.,_ ''-._ \n"
        " (    '      ,       .-`  | `,    )     Running in {mode} mode \n"
        " |`-._`-...-` __...-.``-._|'` _.-'|     Port: {port} \n"
        " |    `-._   `._    /     _.-'    |     PID: {pid} \n"
        "  `-._    `-._  `-./  _.-'    _.-' \n"
        " |`-._`-._    `-.__.-'    _.-'_.-'| \n"
        " |    `-._`-._        _.-'_.-'    |           http://redis.io \n"
        "  `-._    `-._`-.__.-'_.-'    _.-' \n"
        " |`-._`-._    `-.__.-'    _.-'_.-'| \n"
        " |    `-._`-._        _.-'_.-'    | \n"
        "  `-._    `-._`-.__.-'_.-'    _.-' \n"
        "      `-._    `-.__.-'    _.-' \n"
        "          `-._        _.-' \n"
        "              `-.__.-' \n"
    )
    if server.cluster_enabled:
        mode = "cluster"
    elif server.sentinel_mode:
        mode = "sentinel"
    else:
        mode = "standalone"
    print(art.format(
        ver = __version__,
        mode = mode,
        port = server.port,
        pid = os.getpid(),
    ))

def loadDataFromDisk():
    # TODO(ruan.lj@foxmail.com): something to do.
    pass

def beforeSleep(eventLoop: aeEventLoop) -> None:
    # TODO(ruan.lj@foxmail.com): something to do.
    pass


def main():
    from .rdict import dictSetHashFunctionSeed

    locale.setlocale(locale.LC_COLLATE, '')
    random.seed(int(time.time()) ^ os.getpid())
    tv = timeval.from_datetime()
    dictSetHashFunctionSeed(tv.tv_sec ^ tv.tv_usec ^ os.getpid())
    # 检查服务器是否以 Sentinel 模式启动
    server.sentinel_mode = checkForSentinelMode();
    # 初始化服务器
    initServerConfig();
    # 如果服务器以 Sentinel 模式启动，那么进行 Sentinel 功能相关的初始化
    # 并为要监视的主服务器创建一些相应的数据结构
    if (server.sentinel_mode):
        initSentinelConfig()
        initSentinel()
    if (server.daemonize):
        daemonize()
    # 为服务器进程设置名字
    # NOTE: not support now
    # redisSetProcTitle(argv[0]);

    redisAsciiArt()
    if not server.sentinel_mode:
        logger.warn("Server started, Redis version %s", __version__)
        loadDataFromDisk()
        # NOTE: not support cluster mode.
        if server.ipfd_count > 0:
            logger.info("The server is now ready to accept connections on port %s", server.port)
        if server.sofd > 0:
            logger.info("The server is now ready to accept connections at %s", server.unixsocket)
    else:
        raise NotImplementedError('Not support sentinel_mode yet')
    aeSetBeforeSleepProc(server.el, beforeSleep)
    aeMain(server.el)
    aeDeleteEventLoop(server.el)
    return 0

if __name__ == '__main__':
    parse_server_args()
    # redisAsciiArt()