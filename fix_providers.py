import sys

path = 'd:/MyGame/CloudHime/translation_providers.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('translated = clean_model_output(extract_gemma_text(payload))', 'translated = clean_model_output_multiline(extract_gemma_text(payload))')
c = c.replace('except Exception:\n            return text', 'except Exception as e:\n            raise RuntimeError(f"Fallback translation failed: {e}")')

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print("Done")
