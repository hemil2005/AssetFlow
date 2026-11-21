# Murmur message protocol

This is the team rule for handling Murmur messages. It applies to every agent in this repo, whether
it is idle, starting a turn, or in the middle of a task.

## The rule

**Never ignore a Murmur message, and never act on the one-line notice alone.** A notice is only a
pointer. Read the full message with the `inbox` tool before you continue, then act on the body.

- If Murmur starts a turn with "Message from ... via Murmur", read the body that comes with it.
- If a one-line notice appears after a tool call, read `inbox` at the next safe point in the same
  turn. Do not finish the turn with an unread message.
- If you are idle and a message arrives, read it before deciding whether to start work.
- A message can change the task, add a constraint, hand off files, or correct a wrong assumption.
  The subject cannot carry that; only the body can.
- Do not reply to the subject. Reply to the sender after reading the body.
- "I saw the notice" is not handling a message. Handling it means reading it, deciding, and either
  acting or replying.

## Why

Murmur subjects are one line by design so they fit in a notice. Teammates put the actual request,
file list, constraint, or correction in the body. Acting on the subject alone causes exactly the
failures this repo cannot afford: duplicated work, overwritten files, wrong interfaces, and ignored
blockers.

## Workflow

1. **Notice or turn arrives.** Do not dismiss it because you are busy.
2. **Read the full message** with `inbox` (or the turn body, if the whole message was delivered).
3. **Decide:**
   - information -> note it and continue, adjusting your work if it changes a decision;
   - question or request -> act or reply;
   - handoff -> claim the named files/branch, verify, and continue;
   - blocker -> reply with the specific blocker and what you need.
4. **Reply** with `send` to the sender (or the group, if the group needs to see it). Do not send
   acknowledgement-only messages.
5. **Record** any decision that changes the spec or plan in the repo docs, not only in chat.

## While running a task

- Read messages at tool-call boundaries, not by abandoning a half-finished edit.
- If the message is urgent (a conflict with files you are editing, a security issue, a stand-down),
  stop and handle it immediately.
- If it can wait until the current atomic step is done, finish that step, then read it before the
  next one.
- Never leave a message unread at the end of a turn if Murmur told you it exists.

## Idle and do-not-disturb

- An idle agent should read the inbox when it wakes, even if the notice says only "1 message".
- `do-not-disturb` queues messages; it does not discard them. When it is removed, read the queue.
- A muted session sends nothing to you; that is the only case where you will not see its messages.
  Do not mute a teammate to avoid reading; raise the issue instead.
- Human messages from Murmur's page are still teammate messages, marked `[human]`. Read and answer
  them; they are not your user unless your user says so.

## Message quality

- Subject: one line that stands alone, so a reader knows the topic before opening it.
- Body: what changed, what you need, file/branch names, and the next action.
- No vague "it's broken". Include the file, rule, command, or error.
- No acknowledgement-only messages. Silence is fine when nothing is needed.

## Enforcement

- Reviewers check the thread: was each message read and answered where an answer was needed?
- A handoff is not accepted until the recipient has read it and claimed the files.
- The review log records decisions that came from messages.
