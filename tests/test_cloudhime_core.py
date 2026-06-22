import pytest
from CloudHime import is_valid_content, needs_cjk_tight_join

def test_is_valid_content():
    # Test valid content
    assert is_valid_content("Hello") is True
    assert is_valid_content("測試字串") is True
    
    # Test invalid content (assumed behavior: empty or just spaces/symbols)
    assert is_valid_content("") is False
    assert is_valid_content("   ") is False

def test_needs_cjk_tight_join():
    # CJK characters should be tightly joined without spaces
    assert needs_cjk_tight_join("測試", "字串") is True
    assert needs_cjk_tight_join("あいう", "えお") is True
    
    # English words should have spaces between them
    assert needs_cjk_tight_join("Hello", "World") is False
    
    # Mixed cases might depend on implementation, but these are typical
    assert needs_cjk_tight_join("Hello", "測試") is True
    assert needs_cjk_tight_join("測試", "Hello") is True
