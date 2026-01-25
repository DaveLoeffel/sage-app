# Phase 3.9 Testing Guide
## Context-Aware Chat with Intent-Based Optimization

**Created:** January 24, 2026
**Status:** Ready for Testing

---

## Overview

Phase 3.9 implemented context-aware chat with RAG integration and intent-based context optimization. This guide provides test cases to verify the functionality works correctly.

### What to Look For

When testing, verify:
1. **Intent is detected correctly** - Check server logs for "Detected chat intent: X"
2. **Entity hints are extracted** - Check logs for "Extracted N entity hints"
3. **Context is retrieved** - Response should be grounded in real data
4. **No hallucination** - System should say "I don't have that information" for non-existent data

---

## 1. Intent Detection Tests

### Email Intent
These queries should be detected as `email` intent and prioritize email context.

```
Show me my unread emails
What emails did I get from John?
Any messages about the budget?
Show me emails from last week
What did [real contact] email me about?
```

### Followup Intent
These queries should be detected as `followup` intent and prioritize followup context.

```
What followups are overdue?
Who am I waiting to hear back from?
Show me pending followups
What haven't I heard back on?
Who owes me a response?
```

### Meeting Intent
These queries should be detected as `meeting` intent and prioritize meeting/calendar context.

```
What meetings do I have today?
Show me my calendar for tomorrow
What was discussed in my last meeting?
Any meetings this week?
Show me my schedule
```

### Contact Intent
These queries should be detected as `contact` intent and prioritize contact/interaction history.

```
Who is Antonio Ralda?
What do I know about Sam Sweitzer?
Tell me about my interactions with [contact name]
How do I reach [contact name]?
```

### Todo Intent
These queries should be detected as `todo` intent and prioritize task-related context.

```
What tasks do I need to do?
Show me my todo list
What action items are pending?
What's on my plate today?
```

### General Intent
These queries should fall back to `general` intent with balanced context.

```
Hello, how are you?
What can you help me with?
Summarize my day
```

---

## 2. Entity Hints Extraction Tests

### With Email Addresses
The system should extract the email address as a hint.

```
Show me emails from antonio@example.com
What did john.smith@company.com send me?
```

### With Names
The system should extract capitalized names as hints.

```
What did Sarah Johnson say about the project?
Emails from John Smith
Show me my conversation with Mike Chen
```

### With Quoted Subjects
The system should extract quoted strings as hints.

```
Find the email about "Q4 budget review"
Show me messages with subject "meeting notes"
Any emails about "contract renewal"?
```

### Combined Hints
The system should extract multiple hints from complex queries.

```
What did John Smith email me about "the proposal"?
Show messages from sarah@company.com about "budget"
```

---

## 3. Memory & Context Tests

### Past Conversation Recall
Test if the system can recall what was discussed earlier in the conversation.

**Sequence:**
1. Ask: "What followups are overdue?"
2. Wait for response
3. Ask: "Tell me more about the first one"
4. Ask: "What did we just discuss?"

**Expected:** The system should maintain context and understand "the first one" refers to the first followup mentioned.

### Multi-Turn Conversation
Test if context is maintained across multiple turns.

**Sequence:**
1. Ask: "Show me emails from [real contact name]"
2. Ask: "What's the most recent one about?"
3. Ask: "Draft a reply to that"

**Expected:** Each follow-up question should understand the context from previous turns.

### Topic Recall (if memories are indexed)
Test if the system can recall past conversations about a topic.

```
What did we discuss about [topic you've asked about before]?
Remember when I asked about [previous topic]?
```

---

## 4. Negative Tests

These should result in the system saying it doesn't have the information (no hallucination).

### Non-Existent Contacts
```
Show me emails from fake.person@notreal.com
What did Bob Fakename email me about?
Who is John Doesnotexist?
```

### Non-Existent Data
```
Show me the meeting with Santa Claus
What's my followup with the President?
Emails about "topic that doesn't exist in your inbox"
```

**Expected Response:** Something like "I don't see any emails from that person" or "I don't have that information in my database."

---

## 5. Edge Cases

### Ambiguous Queries
```
Show me everything
What's new?
Anything important?
```

### Mixed Intent Queries
```
Show me emails about my meetings
What followups came from that meeting?
Who emailed me about the todo list?
```

### Empty Results
```
Show me emails from today (if none exist)
What meetings do I have on Sunday?
```

---

## How to Verify

### Check Server Logs
When running the backend, look for log lines like:
```
INFO - Detected chat intent: email
INFO - Extracted 2 entity hints: ['John Smith', 'budget']
INFO - Retrieved context for chat (intent=email): 15 emails, 3 contacts, 5 followups, 0 meetings, 0 memories
```

### Check Response Quality
- Response should reference real data from your database
- Names, subjects, and dates should match actual emails/contacts
- System should not invent or hallucinate data

### Check Context in Response
The response should include details that prove it's using real context:
- Actual sender names
- Real email subjects
- Correct dates
- Actual followup contacts

---

## Known Limitations

1. **Memory indexing**: Conversation memories are indexed in the background. New conversations may not immediately appear in memory searches.

2. **Todo context**: Todos are stored in a separate table, not the entity system. Todo queries retrieve meeting and followup context as proxy.

3. **Intent detection**: Uses simple pattern matching. Some edge cases may be misclassified.

4. **Entity extraction**: May extract false positives (e.g., capitalized words that aren't names).

---

## After Testing

Update the roadmap with:
- [ ] Test results
- [ ] Any bugs found
- [ ] Edge cases that need improvement
- [ ] Whether Phase 3.9 is complete

Then proceed to:
- **Phase 4: Sage Orchestrator** - Full multi-agent coordination
- **Phase 3.8: Clarifier Agent** - Ambiguous email detection
