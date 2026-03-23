import sys
c = open('generate_card_images.py','r',encoding='utf-8').read()
checks = [
    ('CARD_TYPE_VISUAL_RULES' in c, 'type-aware rules'),
    ('_detect_vertical_calc' in c, 'vertical calc detector'),
    ('solve_strategy_block' in c, 'dynamic strategy block'),
    ("[:200]" in c, 'expanded truncation 200'),
    ('example_steps' in c, 'full example steps'),
    ('不画完整竖式' not in c, 'old rigid rule removed'),
    ('必须画出简化竖式' in c, 'new vertical calc rule'),
    ('is_vertical_calc' in c, 'vertical calc usage'),
    ('card_type' in c, 'card_type variable'),
]
for ok, name in checks:
    print(f'  {"PASS" if ok else "FAIL"} {name}')
print(f'Total lines: {len(c.splitlines())}')
