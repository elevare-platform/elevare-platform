"""Turn an interview transcript into questions and answers a client can follow.

The candidate's browser saves the conversation as one block of text, a label at the start
of each turn:

    AI: Tell me about your last role.

    Candidate: I managed a team of nine...

This splits it into turns and picks out the questions the AI asked, so a reader sees them
at a glance instead of scrolling a wall of text.

When the labels are missing (a transcript that did not match the recording is replaced by
the recording's own transcript, which has no speaker labels) there is nothing to split,
and the caller shows the plain text instead.
"""

import re
from dataclasses import dataclass

# A speaker label at the start of a line. Only these two exist (see InterviewFlow.jsx).
_TURN_START = re.compile(r"^(AI|Candidate):[ \t]*", re.MULTILINE)
# A question is a sentence that ends in "?". Sentences are cut at ".", "!" or "?".
_QUESTION = re.compile(r"[^.?!]*\?")

AI = "AI"
CANDIDATE = "Candidate"


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str


def parse_turns(transcript: str | None) -> list[Turn]:
    """The conversation as turns, in order. Empty when the text has no speaker labels.

    Two turns in a row by the same speaker (the browser sometimes splits one long answer)
    are joined into one, so a question or an answer reads as a single block.
    """
    if not transcript:
        return []
    matches = list(_TURN_START.finditer(transcript))
    if not matches:
        return []

    turns: list[Turn] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(transcript)
        text = transcript[match.end() : end].strip()
        if not text:
            continue
        speaker = match.group(1)
        if turns and turns[-1].speaker == speaker:
            turns[-1] = Turn(speaker, f"{turns[-1].text}\n\n{text}")
        else:
            turns.append(Turn(speaker, text))
    return turns


def questions_asked(turns: list[Turn]) -> list[str]:
    """Every question the AI asked, in order, one per entry.

    A turn that asks two questions gives two entries. Statements, greetings and sign-offs
    are not questions and are left out; they are still in the full conversation.
    """
    questions: list[str] = []
    for turn in turns:
        if turn.speaker != AI:
            continue
        for sentence in _QUESTION.findall(turn.text):
            question = " ".join(sentence.split()).strip()
            if question:
                questions.append(question)
    return questions
