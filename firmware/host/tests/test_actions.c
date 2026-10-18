#include "kb_actions.h"
#include "test_harness.h"

#include <string.h>

static kb_action_t desktop(kb_action_type_t type, const char *name,
                           uint16_t usage)
{
    kb_action_t action;
    memset(&action, 0, sizeof(action));
    action.type = type;
    (void)strcpy(action.key_name, name);
    action.usage_id = usage;
    return action;
}

TEST(key_press_and_release_resolve_by_key_id)
{
    kb_action_t source = desktop(KB_ACTION_KEY, "a", 0x04U);
    kb_key_action_t entry = {"MX-00-00", &source};
    kb_action_profile_t profile = {&entry, 1U};
    kb_typed_action_t output;
    ASSERT_EQ_U32(KB_ACTION_OK, kb_action_resolve(&profile, "MX-00-00", true, &output));
    ASSERT_EQ_U32(KB_TYPED_ACTION_KEY_PRESS, output.type);
    ASSERT_EQ_U32(0x07U, output.usage_page);
    ASSERT_EQ_U32(0x04U, output.usage);
    ASSERT_EQ_U32(KB_ACTION_OK, kb_action_resolve(&profile, "MX-00-00", false, &output));
    ASSERT_EQ_U32(KB_TYPED_ACTION_KEY_RELEASE, output.type);
}

TEST(consumer_press_and_release_resolve)
{
    kb_action_t source = desktop(KB_ACTION_MEDIA, "vol_up", 0x00e9U);
    kb_key_action_t entry = {"K", &source};
    kb_action_profile_t profile = {&entry, 1U};
    kb_typed_action_t output;
    ASSERT_EQ_U32(KB_ACTION_OK, kb_action_resolve(&profile, "K", true, &output));
    ASSERT_EQ_U32(KB_TYPED_ACTION_CONSUMER_PRESS, output.type);
    ASSERT_EQ_U32(0x0cU, output.usage_page);
    ASSERT_EQ_U32(KB_ACTION_OK, kb_action_resolve(&profile, "K", false, &output));
    ASSERT_EQ_U32(KB_TYPED_ACTION_CONSUMER_RELEASE, output.type);
}

TEST(shortcut_resolves_to_key_with_modifiers)
{
    kb_action_t source = desktop(KB_ACTION_SHORTCUT, "a", 0x04U);
    kb_key_action_t entry = {"K", &source};
    kb_action_profile_t profile = {&entry, 1U};
    kb_typed_action_t output;
    source.modifier_count = 2U; source.modifier_bits[0] = 0U;
    source.modifier_bits[1] = 1U;
    ASSERT_EQ_U32(KB_ACTION_OK,
                  kb_action_resolve(&profile, "K", true, &output));
    ASSERT_EQ_U32(KB_TYPED_ACTION_KEY_PRESS, output.type);
    ASSERT_EQ_U32(3U, output.modifiers);
}

TEST(custom_payload_is_passthrough_only)
{
    const uint8_t payload[] = {0U, 1U, 2U, 0xffU};
    kb_typed_action_t output;
    ASSERT_EQ_U32(KB_ACTION_OK, kb_action_make_custom(payload, sizeof(payload), &output));
    ASSERT_EQ_U32(KB_TYPED_ACTION_CUSTOM, output.type);
    ASSERT_EQ_U32(sizeof(payload), output.payload_length);
    ASSERT_TRUE(memcmp(payload, output.payload, sizeof(payload)) == 0);
}

TEST(oversize_custom_rejected_without_state_change)
{
    uint8_t payload[KB_ACTION_CUSTOM_PAYLOAD_MAX + 1U] = {0U};
    kb_typed_action_t output;
    kb_typed_action_t before;
    memset(&output, 0xa5, sizeof(output));
    before = output;
    ASSERT_EQ_U32(KB_ACTION_VALUE_RANGE, kb_action_make_custom(payload, sizeof(payload), &output));
    ASSERT_TRUE(memcmp(&before, &output, sizeof(output)) == 0);
}

TEST(missing_profile_or_key_rejected_without_state_change)
{
    kb_action_profile_t empty = {NULL, 0U};
    kb_typed_action_t output;
    kb_typed_action_t before;
    memset(&output, 0x5a, sizeof(output)); before = output;
    ASSERT_EQ_U32(KB_ACTION_INVALID_ARGUMENT, kb_action_resolve(&empty, "K", true, &output));
    ASSERT_TRUE(memcmp(&before, &output, sizeof(output)) == 0);
}

TEST(invalid_desktop_action_rejected_without_state_change)
{
    kb_action_t source = desktop(KB_ACTION_KEY, "a", 0x55U);
    kb_key_action_t entry = {"K", &source};
    kb_action_profile_t profile = {&entry, 1U};
    kb_typed_action_t output;
    kb_typed_action_t before;
    memset(&output, 0x33, sizeof(output)); before = output;
    ASSERT_EQ_U32(KB_ACTION_UNKNOWN_NAME, kb_action_resolve(&profile, "K", true, &output));
    ASSERT_TRUE(memcmp(&before, &output, sizeof(output)) == 0);
}

static const test_case_t cases[] = {
    TEST_CASE(key_press_and_release_resolve_by_key_id),
    TEST_CASE(consumer_press_and_release_resolve),
    TEST_CASE(shortcut_resolves_to_key_with_modifiers),
    TEST_CASE(custom_payload_is_passthrough_only),
    TEST_CASE(oversize_custom_rejected_without_state_change),
    TEST_CASE(missing_profile_or_key_rejected_without_state_change),
    TEST_CASE(invalid_desktop_action_rejected_without_state_change)
};
TEST_MAIN("actions", cases)
