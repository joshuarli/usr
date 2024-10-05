CC := unknown-unknown-cosmo-cc
CFLAGS := -Wall -Werror -g
LDFLAGS := -Wl,--as-needed

SRCS := $(PROG).c

all: $(PROG)

su-exec: $(SRCS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f $(PROG)
