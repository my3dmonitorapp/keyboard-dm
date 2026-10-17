#include "kb_events.h"

#include <string.h>

void kb_events_init(kb_event_ring_t *ring)
{
    if (ring != NULL) {
        memset(ring, 0, sizeof(*ring));
    }
}

bool kb_events_push(kb_event_ring_t *ring, const kb_event_t *event)
{
    size_t tail;
    if (ring == NULL || event == NULL) {
        return false;
    }
    if (ring->count == KB_EVENT_RING_CAPACITY) {
        ring->head = (ring->head + 1U) % KB_EVENT_RING_CAPACITY;
        --ring->count;
        ++ring->dropped;
    }
    tail = (ring->head + ring->count) % KB_EVENT_RING_CAPACITY;
    ring->items[tail] = *event;
    ++ring->count;
    return true;
}

bool kb_events_pop(kb_event_ring_t *ring, kb_event_t *event)
{
    if (ring == NULL || event == NULL || ring->count == 0U) {
        return false;
    }
    *event = ring->items[ring->head];
    ring->head = (ring->head + 1U) % KB_EVENT_RING_CAPACITY;
    --ring->count;
    return true;
}

size_t kb_events_count(const kb_event_ring_t *ring)
{
    return ring == NULL ? 0U : ring->count;
}

uint32_t kb_events_dropped(const kb_event_ring_t *ring)
{
    return ring == NULL ? 0U : ring->dropped;
}
