case $- in *i*)
	PATH="$HOME/.local/bin:$PATH"
	export PATH
	if [ "$(tty 2>/dev/null)" = /dev/tty1 ] && [ -z "${WAYLAND_DISPLAY:-}" ] &&
		id -Gn 2>/dev/null | tr ' ' '\n' | grep -qx seat; then
		/usr/local/bin/home-session
	fi
	if [ -x "$HOME/.local/bin/ish" ]; then
		exec "$HOME/.local/bin/ish"
	fi
	;;
esac
