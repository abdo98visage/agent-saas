from app.models.telegram_binding import TelegramBinding


def test_pending_telegram_chat_id_is_not_globally_unique_in_model():
    assert TelegramBinding.__table__.c.telegram_chat_id.unique is not True
