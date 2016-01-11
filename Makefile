PREFIX ?= /usr/local/bin

install: reminder.py
	cp $< $(PREFIX)/reminder
	chmod +x $(PREFIX)/reminder

uninstall:
	rm -f $(PREFIX)/reminder

.PHONY: install uninstall