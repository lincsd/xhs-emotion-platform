"""Fix curly quotes in generate_card_images_v3.py"""
import re

filepath = 'generate_card_images_v3.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace ALL curly quotes with straight quotes
original_len = len(content)
content = content.replace('\u201c', '"')  # left curly double quote
content = content.replace('\u201d', '"')  # right curly double quote
content = content.replace('\u2018', "'")  # left curly single quote
content = content.replace('\u2019', "'")  # right curly single quote

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Fixed curly quotes. File size: {original_len} -> {len(content)} chars')
