from app.assistant import Reply

from .conftest import LEAD, PASSWORD, FakeClaude


def chat(client, message, conversation_id=None):
    response = client.post("/api/chat", json={"message": message, "conversation_id": conversation_id})
    assert response.status_code == 200, response.text
    return response.json()


# ---- public -----------------------------------------------------------------


def test_health_and_config(client):
    health = client.get("/api/health").json()
    assert health == {"status": "ok", "ai_configured": False, "notifications_configured": True, "admin_enabled": True}
    assert client.get("/api/public/config").json()["clinic_name"] == "Brightside Dental & Physio"


def test_widget_and_demo_are_served(client):
    assert "LeadFlow chat widget" in client.get("/widget.js").text
    assert "Demo only" in client.get("/demo").text


def test_offline_answer_is_grounded_and_cited(client):
    data = chat(client, "What time do you open on Saturday?")
    assert data["reply"]["answerable"] and data["reply"]["mode"] == "offline"
    assert data["reply"]["citations"][0]["title"] == "Opening hours"
    assert "9am to 1pm" in data["reply"]["text"]


def test_unknown_question_says_so_and_offers_to_take_details(client):
    data = chat(client, "Do you offer Invisalign braces?")
    assert not data["reply"]["answerable"] and data["reply"]["citations"] == []
    assert data["offer_lead"] is True


def test_booking_intent_offers_the_details_form(client):
    assert chat(client, "I want to book an appointment")["offer_lead"] is True
    assert chat(client, "What are your opening hours?")["offer_lead"] is False


def test_emergency_gets_a_fixed_safe_reply_and_never_calls_claude(make_client):
    claude = FakeClaude(Reply(answerable=True, answer="Should not be used.", cited_ids=["d1p0"]))
    client = make_client(claude)
    data = chat(client, "I have chest pain and can't breathe properly")
    assert data["reply"]["mode"] == "safety" and "999" in data["reply"]["text"]
    assert data["offer_lead"] is False and claude.calls == []


def test_claude_is_used_when_configured_and_conversation_continues(make_client):
    claude = FakeClaude(Reply(answerable=True, answer="We are open 8am to 6pm on weekdays.", cited_ids=["d1p0"]))
    client = make_client(claude)
    first = chat(client, "what are your opening hours")
    assert first["reply"]["mode"] == "claude"
    second = chat(client, "and on Saturday?", first["conversation_id"])
    assert second["conversation_id"] == first["conversation_id"]
    assert len(claude.calls) == 2 and "what are your opening hours" in claude.calls[1]["messages"][0]["content"]


def test_daily_ai_cap_switches_to_offline(make_client):
    claude = FakeClaude(Reply(answerable=True, answer="We are open 8am to 6pm on weekdays.", cited_ids=["d1p0"]))
    client = make_client(claude, ai_daily_limit=1)
    assert chat(client, "what are your opening hours")["reply"]["mode"] == "claude"
    assert chat(client, "what are your opening hours")["reply"]["mode"] == "offline"
    assert len(claude.calls) == 1


def test_chat_validation_and_rate_limit(make_client):
    client = make_client(chat_per_minute=3)
    assert client.post("/api/chat", json={"message": "   "}).status_code == 422
    assert client.post("/api/chat", json={"message": "x" * 1001}).status_code == 422
    for _ in range(3):
        chat(client, "opening hours")
    limited = client.post("/api/chat", json={"message": "opening hours"})
    assert limited.status_code == 429


def test_conversation_length_is_capped(make_client):
    client = make_client(max_messages_per_conversation=4)
    first = chat(client, "opening hours")
    second = chat(client, "opening hours again", first["conversation_id"])
    assert client.post("/api/chat", json={"message": "more", "conversation_id": second["conversation_id"]}).status_code == 429


# ---- leads and notifications ---------------------------------------------------


def test_lead_requires_consent_and_a_real_contact(client):
    refused = client.post("/api/leads", json={**LEAD, "consent": False})
    assert refused.status_code == 422
    assert refused.json()["detail"] == "We need your permission to contact you."  # readable, no pydantic jargon
    assert client.post("/api/leads", json={**LEAD, "contact": "not a contact"}).status_code == 422
    assert client.post("/api/leads", json={**LEAD, "contact": "07700 900123"}).status_code == 201


def test_lead_is_triaged_stored_and_the_team_is_notified(client, admin, webhook):
    created = client.post("/api/leads", json={**LEAD, "reason": "Terrible toothache, can I be seen today?"})
    assert created.status_code == 201 and "priority" not in created.text  # the visitor never sees triage
    lead = client.get("/api/admin/leads", headers=admin).json()[0]
    assert (lead["priority"], lead["category"], lead["status"]) == ("high", "Dental", "new")
    assert lead["notification"]["status"] == "sent" and lead["notification"]["attempts"] == 1
    assert "high priority" in webhook.posts[0][1]["text"]


def test_failed_notification_is_recorded_and_can_be_resent(make_client, webhook):
    webhook.script = [500]
    client = make_client()
    admin = {"Authorization": "Bearer " + client.post("/api/admin/login", json={"password": PASSWORD}).json()["token"]}
    client.post("/api/leads", json=LEAD)
    lead = client.get("/api/admin/leads", headers=admin).json()[0]
    assert lead["notification"]["status"] == "failed" and lead["notification"]["attempts"] == 3
    assert len(webhook.sleeps) == 2

    webhook.script = [200]
    assert client.post(f"/api/admin/leads/{lead['id']}/notify", headers=admin).status_code == 200
    again = client.get("/api/admin/leads", headers=admin).json()[0]
    assert again["notification"]["status"] == "sent" and again["notification"]["attempts"] == 1


def test_lead_is_still_saved_when_no_webhook_is_configured(make_client):
    client = make_client(notify_webhook_url="")
    token = client.post("/api/admin/login", json={"password": PASSWORD}).json()["token"]
    client.post("/api/leads", json=LEAD)
    lead = client.get("/api/admin/leads", headers={"Authorization": f"Bearer {token}"}).json()[0]
    assert lead["notification"]["status"] == "skipped"


def test_lead_rate_limit(make_client):
    client = make_client(leads_per_hour=2)
    assert [client.post("/api/leads", json=LEAD).status_code for _ in range(3)] == [201, 201, 429]


# ---- admin -----------------------------------------------------------------------


def test_admin_requires_a_valid_token(client):
    assert client.get("/api/admin/leads").status_code == 401
    assert client.get("/api/admin/leads", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/admin/login", json={"password": "wrong"}).status_code == 401


def test_admin_is_off_when_no_password_is_set(make_client):
    client = make_client(admin_password="")
    assert client.post("/api/admin/login", json={"password": ""}).status_code in (422, 503)
    assert client.post("/api/admin/login", json={"password": "x"}).status_code == 503
    assert client.get("/api/admin/leads").status_code == 503


def test_login_attempts_are_throttled(make_client):
    client = make_client()
    codes = [client.post("/api/admin/login", json={"password": "wrong"}).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
    assert client.post("/api/admin/login", json={"password": PASSWORD}).status_code == 429


def test_lead_status_workflow(client, admin):
    client.post("/api/leads", json=LEAD)
    lead_id = client.get("/api/admin/leads", headers=admin).json()[0]["id"]
    assert client.patch(f"/api/admin/leads/{lead_id}", json={"status": "booked"}, headers=admin).json()["status"] == "booked"
    assert client.patch(f"/api/admin/leads/{lead_id}", json={"status": "bogus"}, headers=admin).status_code == 422
    assert client.patch("/api/admin/leads/999", json={"status": "closed"}, headers=admin).status_code == 404
    assert len(client.get("/api/admin/leads?status=booked", headers=admin).json()) == 1
    assert client.get("/api/admin/leads?status=new", headers=admin).json() == []


def test_knowledge_base_edits_change_what_the_assistant_can_answer(client, admin):
    assert not chat(client, "Do you offer Invisalign braces?")["reply"]["answerable"]
    created = client.post(
        "/api/admin/documents",
        headers=admin,
        json={"title": "Invisalign", "content": "We offer Invisalign clear braces. A consultation costs £50."},
    )
    assert created.status_code == 201 and created.json()["passages"] == 1
    answer = chat(client, "Do you offer Invisalign braces?")["reply"]
    assert answer["answerable"] and answer["citations"][0]["title"] == "Invisalign"

    doc_id = created.json()["id"]
    client.put(f"/api/admin/documents/{doc_id}", headers=admin, json={"title": "Invisalign", "content": "We no longer offer it."})
    assert "no longer" in chat(client, "Do you offer Invisalign braces?")["reply"]["citations"][0]["snippet"]
    assert client.delete(f"/api/admin/documents/{doc_id}", headers=admin).status_code == 204
    assert not chat(client, "Do you offer Invisalign braces?")["reply"]["answerable"]
    assert client.put("/api/admin/documents/999", headers=admin, json={"title": "x", "content": "y"}).status_code == 404


def test_unanswered_list_and_conversation_history(client, admin):
    first = chat(client, "Do you offer Invisalign braces?")
    chat(client, "What are your opening hours?")
    missed = client.get("/api/admin/unanswered", headers=admin).json()
    assert [m["question"] for m in missed] == ["Do you offer Invisalign braces?"]

    conversations = client.get("/api/admin/conversations", headers=admin).json()
    assert len(conversations) == 2 and any(c["unanswered"] == 1 for c in conversations)
    detail = client.get(f"/api/admin/conversations/{first['conversation_id']}", headers=admin).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert client.get("/api/admin/conversations/nope", headers=admin).status_code == 404


def test_stats(client, admin):
    chat(client, "What are your opening hours?")
    chat(client, "Do you offer Invisalign braces?")
    chat(client, "I have chest pain")  # safety replies don't count towards the answered rate
    client.post("/api/leads", json=LEAD)
    stats = client.get("/api/admin/stats", headers=admin).json()
    assert stats["conversations"] == 3 and stats["assistant_replies"] == 2 and stats["answered_rate"] == 0.5
    assert stats["leads"] == 1 and stats["leads_by_status"]["new"] == 1 and stats["notifications_failed"] == 0
