# reminder

**reminder** is a command to show messages at specified time by Tkinter. It can be used as a todo app.

The data are stored in `~/.reminder/`.

## Install

```
$ sudo apt-get install python-tk
$ supported pip install setproctitle
$ sudo make install
```

## Uninstall
```
$ sudo make uninstall
```

## How to Use

#### get help
```
$ reminder -h
```
#### start daemon
```
$ reminder --start
```

#### stop daemon
```
$ reminder --stop
```

#### notify after 12s
```
$ reminder --after 12s -m "notify...."
```

#### notify at 13 o'clock
```
$ reminder --when 13h0m0s -m "notify...."
```

#### show all todo items
```
$ reminder --list
```

#### show history
```
$ reminder --history
```

## Test
```
$ cd test
$ python -m unittest reminder_test
```

## Todo
Be compatible with python 3.


## License
MIT

## Reference

http://ubuntuforums.org/showthread.php?t=1859585

http://www.oschina.net/translate/making-your-open-source-project-newcomer-friendly

https://wiki.archlinux.org/index.php/Desktop_notifications

http://superuser.com/questions/96151/how-do-i-check-whether-i-am-using-kde-or-gnome

http://askubuntu.com/questions/125062/how-can-i-find-which-desktop-enviroment-i-am-using