#include "kb_events.h"
#include "test_harness.h"

TEST(overflow_drops_oldest_and_preserves_order)
{
    kb_event_ring_t ring;
    kb_event_t event;
    size_t index;
    kb_events_init(&ring);
    for (index = 0U; index < KB_EVENT_RING_CAPACITY + 3U; ++index) {
        event.type = KB_EVENT_KEY_DOWN;
        event.row = 0U;
        event.col = (uint8_t)index;
        event.switch_id = (uint16_t)index;
        event.timestamp_ms = index;
        ASSERT_TRUE(kb_events_push(&ring, &event));
    }
    ASSERT_EQ_U32(KB_EVENT_RING_CAPACITY, kb_events_count(&ring));
    ASSERT_EQ_U32(3U, kb_events_dropped(&ring));
    for (index = 3U; index < KB_EVENT_RING_CAPACITY + 3U; ++index) {
        ASSERT_TRUE(kb_events_pop(&ring, &event));
        ASSERT_EQ_U32(index, event.switch_id);
    }
    ASSERT_TRUE(!kb_events_pop(&ring, &event));
}

static const test_case_t cases[] = {
    TEST_CASE(overflow_drops_oldest_and_preserves_order)
};

TEST_MAIN("events", cases)
