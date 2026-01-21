#!/usr/bin/env python3
import json
import re

with open('backend/outputs/51c4ca18-c688-4d6f-8f8e-54036fee9784/script.json') as f:
    d = json.load(f)

s = d.get('sections', [])
if s:
    manim_code = s[0].get('manim_code', '')
    print(f'Manim code length: {len(manim_code)}')
    
    # Same pattern as in the code
    text_pattern = r'(Text)\s*\(\s*(["\'])((?:(?!\2)[^\\]|\\.)*)\2'
    matches = list(re.finditer(text_pattern, manim_code))
    print(f'Text() matches found: {len(matches)}')
    
    for i, m in enumerate(matches[:5]):
        text = m.group(3)
        print(f'  Match {i+1}: {text[:50]}...' if len(text) > 50 else f'  Match {i+1}: {text}')
