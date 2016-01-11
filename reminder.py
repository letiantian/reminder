#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function

import atexit
import os
import sys
import time
import signal
import sqlite3
import subprocess
import thread
import argparse
import re
import datetime

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
                 home_dir='.', umask=022, verbose=1, use_gevent=False):
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
        except OSError, e:
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
        except OSError, e:
            sys.stderr.write(
                "fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # if sys.platform != 'darwin':  # This block breaks on OS X
        #     # Redirect standard file descriptors
        #     sys.stdout.flush()
        #     sys.stderr.flush()
        #     si = file(self.stdin, 'r')
        #     so = file(self.stdout, 'a+')
        #     if self.stderr:
        #         se = file(self.stderr, 'a+', 0)
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
        file(self.pidfile, 'w+').write("%s\n" % pid)

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
            pf = file(self.pidfile, 'r')
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
        except OSError, err:
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
            pf = file(self.pidfile, 'r')
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

#
# config
# 
CONFIG = {
    'repeat'  : 3,
    'dir'     : os.getenv('HOME') + '/.reminder',
    'pidfile' : 'reminder.pid',
    'dbfile'  : 'reminder.db',
    'sleep'   : 40,
    'interval': 60
}

HISTORY = 'history'
ITEMS   = 'items'

def parse_arguments(*arg):
    """
    --start
    --stop
    --restart
    --time  13h24m23s
    --after 13h
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
    parser.add_argument("-w", "--when",
                        help="When to remind")
    parser.add_argument("-a", "--after",
                        help="When to remind")
    parser.add_argument("-r", "--repeat", 
                        type=int,
                        help="repeat")
    parser.add_argument("content",  nargs='?',
                        help="content")
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
    """
    """
    d2t = {
        'cinnamon': ['notify-send'],
    }
    def __notify():
        # detect desktop env
        desktop = os.getenv('DESKTOP_SESSION') + ', ' +os.getenv('XDG_CURRENT_DESKTOP')
        desktop = desktop.lower()
        tool = None
        for d in d2t:
            if d in desktop:
                tool = d2t[d]
                break
        if not tool:
            return

        for _ in range(repeat):
            subprocess.Popen(tool +[msg], stdout=subprocess.PIPE)
            time.sleep(CONFIG['interval'])

    if threadable:
        thread.start_new_thread(__notify, ()) 
    else:
        __notify()



def get_conn():
    """
    """
    return sqlite3.connect( CONFIG['dir'] + '/' + CONFIG['dbfile'] )

def close_conn(conn):
    """
    """
    if conn:
        conn.close()

def create_db(conn):
    """
    """
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

def insert(conn, table, when, msg, repeat):
    """
    """
    sql = "INSERT INTO {0}(whento, msg, repeat) VALUES (?,?,?)".format(table)
    try:
        if conn is None:
            conn = get_conn()
        
        cur = conn.cursor()    
        cur.execute(sql, (when, msg, repeat))
        
        conn.commit()           
        
    except sqlite3.Error, e:
        print("Error %s:" % e.args[0])
        sys.exit(1)

    # finally:
    #     if conn:
    #         conn.close()

def select_one(conn):
    """
    """

    sql = "SELECT id, whento, msg, repeat FROM {0} ORDER BY whento LIMIT 1".format(ITEMS)
    try:        
        cur = conn.cursor()    
        cur.execute(sql)

        return cur.fetchone()     # 若无数据，返回None，否则返回一个元组            
        
    except sqlite3.Error, e:
        print("Error %s:" % e.args[0])
        sys.exit(1)

def delete(conn, table, item_id):
    sql = 'DELETE FROM {0} WHERE id=?'.format(table)
    cur = conn.cursor()    
    cur.execute(sql, (item_id,))
    conn.commit()        

def move(conn, item_id, when, msg, repeat):
    """
    """
    insert(conn, HISTORY, when, msg, repeat)
    delete(conn, ITEMS, item_id)

def prepare():
    """ """
    if not os.path.exists(CONFIG['dir']):
        os.makedirs(CONFIG['dir'])

class ReminderDaemon(Daemon):
    def run(self):
        prepare()
        conn = get_conn()
        create_db( conn )
        try:
            import setproctitle
            setproctitle.setproctitle('reminder')
        except:
            pass

        while True:
            item = select_one(conn)
            if item:
                item_id, when, msg, repeat = item
                
                now = datetime.datetime.now()
                now = date2int(now)

                if now >= when:  
                    notify(msg, repeat)
                    move(conn, item_id, when, msg, repeat)

            time.sleep(CONFIG['sleep'])


def main():
    """
    """
    pidfile = CONFIG['dir']+'/'+CONFIG['pidfile']
    # print(pidfile)
    reminder = ReminderDaemon(pidfile)
    prepare()
    conn = get_conn()
    create_db( conn )
    args = parse_arguments()
    if args.start:
        reminder.start()
    elif args.stop:
        reminder.stop()
    elif args.restart:
        reminder.restart()
    else:
        if not args.content:
            raise Exception('The content should be gived')
        # now, args.content has content
        if args.when or args.after:
            when = parse_time(args.when, args.after)
        else:
            now = datetime.datetime.now()
            when = date2int(now)            
        repeat = CONFIG['repeat']
        if args.repeat:
            repeat = args.repeat
        insert(conn, ITEMS, when, args.content, repeat)

    close_conn(conn)


if __name__ == '__main__':
    main()
