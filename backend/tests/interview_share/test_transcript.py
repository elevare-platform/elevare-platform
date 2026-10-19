"""Splitting a transcript into turns, and picking out the questions the AI asked."""

import pytest

from app.modules.interview_share.transcript import Turn, parse_turns, questions_asked

CONVERSATION = (
    "AI: Welcome. Tell me about your last role?\n\n"
    "Candidate: I managed a team of nine reps.\n\n"
    "AI: Thanks. What was the hardest part? And how did you handle it?\n\n"
    "Candidate: Hitting the monthly targets."
)


def test_a_conversation_is_split_into_turns_in_order():
    turns = parse_turns(CONVERSATION)

    assert [turn.speaker for turn in turns] == ["AI", "Candidate", "AI", "Candidate"]
    assert turns[1] == Turn("Candidate", "I managed a team of nine reps.")


def test_the_questions_the_ai_asked_are_picked_out_one_per_entry():
    questions = questions_asked(parse_turns(CONVERSATION))

    assert questions == [
        "Tell me about your last role?",
        "What was the hardest part?",
        "And how did you handle it?",
    ]


def test_greetings_and_statements_are_not_questions():
    turns = parse_turns("AI: Welcome to the interview. Let's begin.\n\nCandidate: Ready.")

    assert questions_asked(turns) == []


def test_only_the_ai_asks_questions_not_the_candidate():
    turns = parse_turns("AI: Introduce yourself.\n\nCandidate: Do you want my full name?")

    assert questions_asked(turns) == []


def test_two_turns_in_a_row_by_the_same_speaker_are_joined():
    turns = parse_turns("AI: First part of the question\n\nAI: and the rest of it?\n\nCandidate: Yes.")

    assert [turn.speaker for turn in turns] == ["AI", "Candidate"]
    assert turns[0].text == "First part of the question\n\nand the rest of it?"
    assert questions_asked(turns) == ["First part of the question and the rest of it?"]


def test_a_multi_line_answer_stays_in_one_turn():
    turns = parse_turns("AI: Describe a hard sale?\n\nCandidate: It was long.\nIt took a year.\n\nAI: Thanks.")

    assert turns[1].text == "It was long.\nIt took a year."


@pytest.mark.parametrize("text", [None, "", "   ", "no speaker labels in this recording transcript"])
def test_text_without_speaker_labels_gives_no_turns(text):
    assert parse_turns(text) == []
    assert questions_asked(parse_turns(text)) == []


def test_a_label_in_the_middle_of_a_line_is_not_a_new_turn():
    turns = parse_turns("AI: The word AI: appears in the middle of this sentence?")

    assert len(turns) == 1


def test_empty_turns_are_dropped():
    turns = parse_turns("AI: \n\nCandidate: Hello there.")

    assert turns == [Turn("Candidate", "Hello there.")]


def test_question_whitespace_is_tidied():
    turns = parse_turns("AI: Tell me   about\nyour   last role?")

    assert questions_asked(turns) == ["Tell me about your last role?"]
