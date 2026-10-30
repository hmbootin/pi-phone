"""Every spoken string in one place. Keep them short: the listener is a toddler."""

from __future__ import annotations

CALLING = "Calling {name}."
NO_ANSWER = "{name} isn't answering right now. Let's try again later. Bye bye!"
BUSY = "{name} is busy right now. Let's try again later. Bye bye!"
CALL_FAILED = "Oops, the phone couldn't connect. Let's try again later. Bye bye!"
LINE_BUSY = "Someone is already on the phone. Try again in a minute."
NOTHING_THERE = "Nothing is on that button. Try another one!"
NOT_ALLOWED = "{name} can't talk right now. Let's try again later. Bye bye!"
QUIET_HOURS = "It's sleepy time. The phone is resting. Let's call tomorrow. Bye bye!"
DAILY_CAP = "That's a lot of calls today! Let's call again tomorrow. Bye bye!"
TIME_WARNING_BEEP = "beep"
GOODBYE = "Time's up! Bye bye!"
FEATURE_FAILED = "Oops, that didn't work. Try again later."

INBOUND_UNKNOWN = "Sorry, this number can't take calls from you. Goodbye."
INBOUND_UNKNOWN_VOICEMAIL = (
    "Sorry, this number can't take calls from you. "
    "Leave a message for the parents after the beep, then hang up."
)
INBOUND_QUIET_HOURS = "It's sleepy time here. Please call back later. Goodbye."
INBOUND_DND = "They can't come to the phone right now. Please call back later. Goodbye."
INBOUND_BUSY = "They're on the phone right now. Please call back later. Goodbye."
INBOUND_NO_ANSWER = "They're busy right now. Leave a message after the beep, then hang up. Goodbye!"

SECRET_PROMPT = "Tell {name} your secret after the beep, then hang up the phone."
SECRET_THANKS = "Got it! Your secret is safe. Bye bye!"
MAILBOX_EMPTY = "No new messages. Bye bye!"
MAILBOX_INTRO = "You have {count} new messages."
MAILBOX_FROM = "Message from {name}."
MAILBOX_DONE = "That's all your messages. Bye bye!"
WEATHER = "Right now in {place} it's {temp} degrees and {condition}. Today's high is {high}."
WEATHER_UNAVAILABLE = "I can't see the sky right now. Try again later!"
FUN_FACT = "Here's a fun fact about {topic}. {fact}"
SONG = "La la la, la la la. That's my song. Bye bye!"
TEST_CALL = "This is a test call from Tin Can. The line works. Bye bye!"
WELCOME = "Hello! Press a number to call someone."

STATIC = {
    "no_answer": NO_ANSWER,
    "busy": BUSY,
    "call_failed": CALL_FAILED,
    "line_busy": LINE_BUSY,
    "nothing_there": NOTHING_THERE,
    "quiet_hours": QUIET_HOURS,
    "daily_cap": DAILY_CAP,
    "goodbye": GOODBYE,
    "feature_failed": FEATURE_FAILED,
    "inbound_unknown": INBOUND_UNKNOWN,
    "inbound_unknown_voicemail": INBOUND_UNKNOWN_VOICEMAIL,
    "inbound_quiet_hours": INBOUND_QUIET_HOURS,
    "inbound_dnd": INBOUND_DND,
    "inbound_busy": INBOUND_BUSY,
    "inbound_no_answer": INBOUND_NO_ANSWER,
    "secret_thanks": SECRET_THANKS,
    "mailbox_empty": MAILBOX_EMPTY,
    "mailbox_done": MAILBOX_DONE,
    "weather_unavailable": WEATHER_UNAVAILABLE,
    "song": SONG,
    "test_call": TEST_CALL,
    "welcome": WELCOME,
}
"""Prompts with no placeholders; `tincan render-prompts` pre-renders these."""
