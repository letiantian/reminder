# reminder

**reminder** is a tool to show message at specified time. It depends on  notification tool in users's Linux Desktop edition. For example, for `Cinnamon` `notify-send` is used to show notifications.

The data are stored in `~/.reminder/`.


## Install

```
$ sudo make install
```

## Uninstall
```
$ sudo make uninstall
```

## How to Use

### get help
```
$ reminder -h
```
### start daemon
```
$ reminder --start
```

### stop daemon
```
$ reminder --stop
```

### notify after 12s
```
$ reminder --after 12s "notify...."
```

### notify at 13 o'clock
```
$ reminder --when 13h0m0s "notify...."
```

## Test
```
$ cd test
$ python -m unittest reminder_test
```

## Todo
Be compatible with python 3.

## Contributing
`reminder` need many improvements.

For example, currently, only `Cinnamon` is supported. More Desktops need to be supported. Please feel free to modify the function `notify`.

## License
MIT

## Reference

http://ubuntuforums.org/showthread.php?t=1859585

http://www.oschina.net/translate/making-your-open-source-project-newcomer-friendly

https://wiki.archlinux.org/index.php/Desktop_notifications

http://superuser.com/questions/96151/how-do-i-check-whether-i-am-using-kde-or-gnome

http://askubuntu.com/questions/125062/how-can-i-find-which-desktop-enviroment-i-am-using