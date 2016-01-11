#!/usr/bin/env python
# coding: utf-8

from __future__ import (print_function, unicode_literals)

import atexit
import os
import sys
import time
import signal
import sqlite3
import subprocess
import threading
import argparse
import re
import datetime

try:
    import Tkinter
except:
    import tkinter as Tkinter

try:
    reload(sys)
    sys.setdefaultencoding('utf-8')
except:
    pass

#
# config
# 
CONFIG = {
    'repeat'  : 1,
    'dir'     : os.getenv('HOME') + '/.reminder',
    'pidfile' : 'reminder.pid',
    'dbfile'  : 'reminder.db',
    'sleep'   : 40,
    'interval': 60
}

HISTORY = 'history'
ITEMS   = 'items'

PY2 = sys.version_info[0] == 2
if not PY2:
    # Python 3.x and up
    xrange = range

    def as_text(v):  ## 生成unicode字符串
        if v is None:
            return None
        elif isinstance(v, bytes):
            return v.decode('utf-8', errors='ignore')
        elif isinstance(v, str):
            return v
        else:
            raise ValueError('Unknown type %r' % type(v))


else:
    # Python 2.x
    xrange = xrange

    def as_text(v):
        if v is None:
            return None
        elif isinstance(v, unicode):
            return v
        elif isinstance(v, str):
            return v.decode('utf-8', errors='ignore')
        else:
            raise ValueError('Invalid type %r' % type(v))



#
# Daemon class
# https://github.com/serverdensity/python-daemon
#

class Daemon(object):
    """
    A generic daemon class.
    Usage: subclass the Daemon class and override the run() method
    """
    def __init__(self, pidfile, stdin=os.devnull,
                 stdout=os.devnull, stderr=os.devnull,
                 home_dir='.', umask=0o22, verbose=1, use_gevent=False):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile
        self.home_dir = home_dir
        self.verbose = verbose
        self.umask = umask
        self.daemon_alive = True
        self.use_gevent = use_gevent

    def daemonize(self):
        """
        Do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(
                "fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # Decouple from parent environment
        os.chdir(self.home_dir)
        os.setsid()
        os.umask(self.umask)

        # Do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Exit from second parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(
                "fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # if sys.platform != 'darwin':  # This block breaks on OS X
        #     # Redirect standard file descriptors
        #     sys.stdout.flush()
        #     sys.stderr.flush()
        #     si = open(self.stdin, 'r')
        #     so = open(self.stdout, 'a+')
        #     if self.stderr:
        #         se = open(self.stderr, 'a+', 0)
        #     else:
        #         se = so
        #     os.dup2(si.fileno(), sys.stdin.fileno())
        #     os.dup2(so.fileno(), sys.stdout.fileno())
        #     os.dup2(se.fileno(), sys.stderr.fileno())

        def sigtermhandler(signum, frame):
            self.daemon_alive = False
            sys.exit()

        if self.use_gevent:
            import gevent
            gevent.reinit()
            gevent.signal(signal.SIGTERM, sigtermhandler, signal.SIGTERM, None)
            gevent.signal(signal.SIGINT, sigtermhandler, signal.SIGINT, None)
        else:
            signal.signal(signal.SIGTERM, sigtermhandler)
            signal.signal(signal.SIGINT, sigtermhandler)

        if self.verbose >= 1:
            print("Started")

        # Write pidfile
        atexit.register(
            self.delpid)  # Make sure pid file is removed if we quit
        pid = str(os.getpid())
        open(self.pidfile, 'w+').write("%s\n" % pid)

    def delpid(self):
        os.remove(self.pidfile)

    def start(self, *args, **kwargs):
        """
        Start the daemon
        """

        if self.verbose >= 1:
            print("Starting...")

        # Check for a pidfile to see if the daemon already runs
        try:
            pf = open(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None

        if pid:
            message = "pidfile %s already exists. Is it already running?\n"
            sys.stderr.write(message % self.pidfile)
            sys.exit(1)

        # Start the daemon
        self.daemonize()
        self.run(*args, **kwargs)

    def stop(self):
        """
        Stop the daemon
        """

        if self.verbose >= 1:
            print("Stopping...")

        # Get the pid from the pidfile
        pid = self.get_pid()

        if not pid:
            message = "pidfile %s does not exist. Not running?\n"
            sys.stderr.write(message % self.pidfile)

            # Just to be sure. A ValueError might occur if the PID file is
            # empty but does actually exist
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)

            return  # Not an error in a restart

        # Try killing the daemon process
        try:
            i = 0
            while 1:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
                i = i + 1
                if i % 10 == 0:
                    os.kill(pid, signal.SIGHUP)
        except OSError as err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                print(str(err))
                sys.exit(1)

        if self.verbose >= 1:
            print("Stopped")

    def restart(self):
        """
        Restart the daemon
        """
        self.stop()
        self.start()

    def get_pid(self):
        try:
            pf = open(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None
        return pid

    def is_running(self):
        pid = self.get_pid()

        if pid is None:
            print('Process is stopped')
        elif os.path.exists('/proc/%d' % pid):
            print('Process (pid %d) is running...' % pid)
        else:
            print('Process (pid %d) is killed' % pid)

        return pid and os.path.exists('/proc/%d' % pid)

    def run(self):
        """
        You should override this method when you subclass Daemon.
        It will be called after the process has been
        daemonized by start() or restart().
        """
        raise NotImplementedError
#
# end of Daemon class
#


class DB(object):

    @staticmethod
    def create_table(conn):
        """ Create table """
        items_sql = '''
        CREATE TABLE IF NOT EXISTS items(
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            whento   INTEGER,
            msg      TEXT,
            repeat   INTEGER
        );
        '''

        history_sql = '''
        CREATE TABLE IF NOT EXISTS history(
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            whento   INTEGER,
            msg      TEXT,
            repeat   INTEGER
        );
        '''
        
        cur = conn.cursor()    
        cur.execute(items_sql)
        cur.execute(history_sql)
        
        conn.commit() 


    @staticmethod
    def insert(conn, table, when, msg, repeat):
        """ insert data into a table """
        sql = "INSERT INTO {0}(whento, msg, repeat) VALUES (?,?,?)".format(table)
            
        cur = conn.cursor()    
        cur.execute(sql, (when, msg, repeat))
        
        conn.commit()         


    @staticmethod
    def select_one(conn):
        """ """
        sql = "SELECT id, whento, msg, repeat FROM {0} ORDER BY whento LIMIT 1".format(ITEMS)     
        cur = conn.cursor()    
        cur.execute(sql)

        return cur.fetchone()     # 若无数据，返回None，否则返回一个元组            
            

    @staticmethod
    def show_all(conn, table):
        """ """
        sql = "SELECT whento, msg FROM {0} ORDER BY whento".format(table)        
        cur = conn.cursor()    
        for row in cur.execute(sql):
            row = [str(item) for item in row]
            print(' -> '.join(row))

    @staticmethod
    def clean_all(conn, table):
        """ Clean outdated data """
        timepoint = date2int( datetime.datetime.now() ) - CONFIG['sleep']*3
        items_sql = 'DELETE FROM {0} WHERE whento < ?'.format(ITEMS)
        history_sql = 'DELETE FROM {0}'.format(HISTORY)
        cur = conn.cursor()
        cur.execute(items_sql, (timepoint,))
        cur.execute(history_sql)
        conn.commit()


    @staticmethod
    def delete(conn, table, item_id):
        """ Delete data by id """
        sql = 'DELETE FROM {0} WHERE id=?'.format(table)
        cur = conn.cursor()    
        cur.execute(sql, (item_id,))
        conn.commit()        


    @staticmethod
    def move(conn, item_id, when, msg, repeat):
        """ Move data from ITEMS to HISTORY """
        DB.insert(conn, HISTORY, when, msg, repeat)
        DB.delete(conn, ITEMS, item_id)


class ReminderDaemon(Daemon):
    def run(self):
        prepare()
        conn = get_conn()
        DB.create_table( conn )
        try:
            import setproctitle
            setproctitle.setproctitle('reminder daemon')
        except:
            pass

        while True:
            item = DB.select_one(conn)
            if item:
                item_id, when, msg, repeat = item
                
                now = datetime.datetime.now()
                now = date2int(now)

                if now >= when:  
                    notify(msg, repeat)
                    DB.move(conn, item_id, when, msg, repeat)

            time.sleep(CONFIG['sleep'])


def prepare():
    """ """
    if not os.path.exists(CONFIG['dir']):
        os.makedirs(CONFIG['dir'])

def parse_arguments(*arg):
    """
    --start
    --stop
    --restart
    --time  13h24m23s
    --after 360s
    --repeat 4
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", 
                        help="Start daemon", 
                        action="store_true")
    parser.add_argument("--stop", 
                        help="Stop daemon", 
                        action="store_true")
    parser.add_argument("--restart", 
                        help="Restart daemon", 
                        action="store_true")
    
    parser.add_argument("--list", 
                        help="List all items", 
                        action="store_true")
    parser.add_argument("--history", 
                        help="List all history", 
                        action="store_true")
    parser.add_argument("--clean", 
                        help="Clean history", 
                        action="store_true")

    parser.add_argument("-w", "--when",
                        help="Reach and notify")
    parser.add_argument("-a", "--after",
                        help="After and notify")
    parser.add_argument("-r", "--repeat", 
                        type=int,
                        help="The times to notify the same message")
    parser.add_argument("-m", "--message",
                        help="Message to be notified")
    return parser.parse_args(*arg)

def valid_datetime(year, month, day, hour, minute, second):
    try:
        datetime.datetime(year, month, day, hour, minute, second)
        return True
    except ValueError:
        return False

def date2int(now):
    if isinstance(now, dict):
        result = "{:4d}{:2d}{:2d}{:2d}{:2d}{:2d}".format(now['year'], now['month'], now['day'], now['hour'], now['minute'], now['second'])
    else:
        if not isinstance(now, datetime.datetime):      
            now = datetime.datetime.now()
        result = "{:4d}{:2d}{:2d}{:2d}{:2d}{:2d}".format(now.year, now.month, now.day, now.hour, now.minute, now.second)
    result = result.replace(' ', '0')
    return int(result)

def parse_time(when, after):
    _short_seq = ('Y', 'M', 'D','h', 'm', 's')
    _long_seq  = ('year', 'month', 'day','hour', 'minute', 'second')
    def __parse(s):
        p1 = re.compile(r'(?P<year>\d*)Y(?P<month>\d*)M(?P<day>\d*)D(?P<hour>\d*)h(?P<minute>\d*)m(?P<second>\d*)s')
        p2 = re.compile(r'(?P<month>\d*)M(?P<day>\d*)D(?P<hour>\d*)h(?P<minute>\d*)m(?P<second>\d*)s')
        p3 = re.compile(r'(?P<day>\d*)D(?P<hour>\d*)h(?P<minute>\d*)m(?P<second>\d*)s')
        p4 = re.compile(r'(?P<hour>\d*)h(?P<minute>\d*)m(?P<second>\d*)s')
        p5 = re.compile(r'(?P<minute>\d*)m(?P<second>\d*)s')
        p6 = re.compile(r'(?P<second>\d*)s')

        for pat in (p1, p2, p3, p4, p5, p6):
            result = pat.search(s)
            if result:
                gd = result.groupdict()
                r = {}
                for k in gd:
                    r[k] = int(gd[k])
                return r

        raise Exception('invalid format of time')


    now = datetime.datetime.now()
    if when:
        now = dict(
                year   = now.year,
                month  = now.month,
                day    = now.day,
                hour   = now.hour,
                minute = now.minute,
                second = now.second
            )
        when = __parse(when)

        for k in _long_seq:
            if k in when:
                now[k] = when[k]

        if valid_datetime(now['year'], now['month'], now['day'], 
                          now['hour'], now['minute'], now['second'] ):
            return date2int(now)
        else:
            raise Exception('invalid datetime')

    # from now
    if after:
        after = __parse(after)
        for _ in _long_seq:
            after.setdefault(_, 0)
        # print(after)
        now += datetime.timedelta(days=after['day'], hours=after['hour'], 
                                  minutes=after['minute'], seconds=after['second'])
        return date2int(now)


def notify(msg, repeat, threadable = True):
    """ Notify by Tkinter """
    def __show():
        root = Tkinter.Tk(className ="reminder")
        foo = Tkinter.Label(root, text=msg, font=('', 16, "bold"))
        foo.pack()
        root.geometry(("%dx%d")%(root.winfo_screenwidth(),root.winfo_screenheight()))
        root.mainloop()

    def __notify():
        for _ in range(repeat):
            t = threading.Thread(target=__show, args=())
            t.start()
            time.sleep(CONFIG['interval'])

    if threadable:
        t = threading.Thread(target=__notify, args=())
        t.start()
    else:
        __notify()


def get_conn():
    """ Get sqlite connection """
    return sqlite3.connect( CONFIG['dir'] + '/' + CONFIG['dbfile'] )


def close_conn(conn):
    """ Close sqlite connection """
    if conn:
        conn.close()


def main():
    """ I am main """
    pidfile = CONFIG['dir']+'/'+CONFIG['pidfile']
    # print(pidfile)
    reminder = ReminderDaemon(pidfile)
    prepare()
    conn = get_conn()
    DB.create_table( conn )

    argv = sys.argv
    if len(argv) == 1:
        argv.append('-h')

    args = parse_arguments(argv[1:])

    if args.start:
        reminder.start()
    elif args.stop:
        reminder.stop()
    elif args.restart:
        reminder.restart()
    elif args.list:
        DB.show_all(conn, ITEMS)
    elif args.history:
        DB.show_all(conn, HISTORY)
    elif args.clean:
        DB.clean_all(conn, HISTORY)
    else:
        if not args.message:
            raise Exception('The content should be gived')
        # now, args.message has content
        if args.when or args.after:
            when = parse_time(args.when, args.after)
        else:
            now = datetime.datetime.now()
            when = date2int(now)            
        repeat = CONFIG['repeat']
        if args.repeat:
            repeat = args.repeat
        DB.insert(conn, ITEMS, when, as_text(args.message), repeat)

    close_conn(conn)


if __name__ == '__main__':
    main()
