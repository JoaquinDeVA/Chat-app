CC      = gcc
CFLAGS  = -Wall -Wextra -g
LIBS    = -lncursesw -lpthread

SRCS    = main.c protocol.c network.c app_state.c tui.c
OBJS    = $(SRCS:.c=.o)
TARGET  = cli7

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(LIBS)

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all clean
