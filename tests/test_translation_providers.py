from translation_providers import GoogleTranslationProvider


def test_google_provider_does_not_expose_stream_translation():
    provider = GoogleTranslationProvider()

    assert not hasattr(provider, "translate_stream")
