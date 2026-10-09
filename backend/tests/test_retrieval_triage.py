from app.retrieval import PassageRecord, chunk, search, tokenize
from app.triage import emergency_reply, is_emergency, triage_lead, wants_contact

PASSAGES = [
    PassageRecord("d1p0", "Opening hours", "Open Monday to Friday from 8am to 6pm. Closed on Sundays."),
    PassageRecord("d2p0", "Prices: dental", "A new patient check-up costs £65. Whitening is £250."),
    PassageRecord("d3p0", "Parking", "Free parking behind the clinic for two hours."),
]


def test_tokenize_drops_stopwords_and_stems():
    assert tokenize("What are the opening hours?") == ["open", "hour"]


def test_search_finds_the_right_passage():
    hits = search("when are you open on sundays", PASSAGES)
    assert hits[0].id == "d1p0"
    assert hits[0].coverage > 0.5


def test_search_returns_nothing_for_unrelated_questions():
    assert search("do you offer invisalign", PASSAGES) == []
    assert search("", PASSAGES) == []


def test_chunk_splits_long_text_and_keeps_short_paragraphs():
    long_text = " ".join(f"Sentence number {i} is here." for i in range(60))
    pieces = chunk(long_text, max_chars=300)
    assert len(pieces) > 3
    assert all(len(p) <= 300 for p in pieces)
    assert chunk("One.\n\nTwo.") == ["One.\n\nTwo."]  # short paragraphs merge


def test_emergency_detection():
    assert is_emergency("I have chest pain and feel dizzy")
    assert is_emergency("my face is swollen")
    assert not is_emergency("how much is a check-up")
    assert "999" in emergency_reply("chest pain", "01234 567890")
    assert "116 123" in emergency_reply("I feel suicidal", "01234 567890")


def test_wants_contact():
    assert wants_contact("Can I book an appointment?")
    assert not wants_contact("What are your opening hours?")
    assert not wants_contact("How much is a new patient check-up?")  # a price question is not a booking request


def test_triage_matches_whole_words_only():
    # 'email' contains 'ai' and 'mail'; 'capital' contains 'api'. None of that should matter here.
    result = triage_lead("Please reply by email about the capital works.", None)
    assert result["category"] == "General enquiry"
    assert result["priority"] == "low"


def test_triage_priorities_and_categories():
    urgent = triage_lead("Terrible toothache since last night, can I be seen today?", None)
    assert (urgent["priority"], urgent["category"]) == ("high", "Dental")
    booking = triage_lead("I would like to book a physio appointment for my knee", "Tuesday morning")
    assert (booking["priority"], booking["category"]) == ("medium", "Physiotherapy")
    assert triage_lead("x" * 10 + " call me back", None)["category"] == "General enquiry"
    assert len(triage_lead("word " * 200, None)["summary"]) <= 200


def test_triage_knows_consultations_and_invisalign():
    result = triage_lead("Do you do Invisalign? I would like a consultation.", None)
    assert (result["category"], result["priority"]) == ("Dental", "medium")
