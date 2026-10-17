CC ?= cc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer
CPPFLAGS += -I../shared/include -I.

BUILD_DIR := build
SHARED_SOURCES := ../shared/src/kb_crc32.c ../shared/src/kb_config.c \
	../shared/src/kb_events.c ../shared/src/kb_scanner.c ../shared/src/kb_boot.c
COMMON_SOURCES := $(SHARED_SOURCES) fake_hal.c
TEST_SOURCES := $(wildcard tests/test_*.c)
TEST_BINARIES := $(patsubst tests/%.c,$(BUILD_DIR)/%,$(TEST_SOURCES))

.PHONY: all test clean

all: $(TEST_BINARIES)

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/test_%: tests/test_%.c $(COMMON_SOURCES) | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ -o $@

test: all
	@set -e; total=0; for binary in $(TEST_BINARIES); do \
		./$$binary; total=$$((total + 1)); \
	done; echo "all $$total test binaries passed"

clean:
	rm -rf $(BUILD_DIR)
