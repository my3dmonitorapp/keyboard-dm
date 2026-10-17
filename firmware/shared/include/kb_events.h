#ifndef KB_EVENTS_H
#define KB_EVENTS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define KB_EVENT_RING_CAPACITY 64U

typedef enum {
    KB_EVENT_KEY_DOWN = 0,
    KB_EVENT_KEY_UP
} kb_event_type_t;

typedef struct {
    kb_event_type_t type;
    uint8_t row;
    uint8_t col;
    uint16_t switch_id;
    uint64_t timestamp_ms;
} kb_event_t;

typedef struct {
    kb_event_t items[KB_EVENT_RING_CAPACITY];
    size_t head;
    size_t count;
    uint32_t dropped;
} kb_event_ring_t;

void kb_events_init(kb_event_ring_t *ring);
bool kb_events_push(kb_event_ring_t *ring, const kb_event_t *event);
bool kb_events_pop(kb_event_ring_t *ring, kb_event_t *event);
size_t kb_events_count(const kb_event_ring_t *ring);
uint32_t kb_events_dropped(const kb_event_ring_t *ring);

#endif
