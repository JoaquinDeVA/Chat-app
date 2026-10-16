CC       ?= gcc
CFLAGS   ?= -std=c11 -Wall -Wextra -Wformat=2 -Werror -g
LIBS      = -lncurses -lpthread

LIB_SRCS  = json.c protocol.c session.c network.c config.c
LIB_OBJS  = $(LIB_SRCS:.c=.o)
APP_OBJS  = $(LIB_OBJS) tui.o main.o
TARGET    = chat-client
TEST_BIN  = tests/run_tests

all: $(TARGET)

$(TARGET): $(APP_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(LIBS)

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

# Unit tests: everything except the ncurses interface.
$(TEST_BIN): tests/run_tests.c tests/check.h $(LIB_OBJS)
	$(CC) $(CFLAGS) -I. -o $@ tests/run_tests.c $(LIB_OBJS) -lpthread

test: $(TEST_BIN)
	./$(TEST_BIN)

clean:
	rm -f *.o $(TARGET) $(TEST_BIN)

.PHONY: all test clean
