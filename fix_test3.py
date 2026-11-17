with open('agent_access/tests/test_a1_tokens.py', 'r') as f:
    content = f.read()

# Find the exact position and replace
# The pattern is:
#     assert "<script>" not in html
#     assert "<script>" in html
# We need to change the second line to check for <script>

idx = content.find('assert "<script>" not in html\n    assert "<script>" in html')
if idx >= 0:
    # Replace from that point
    old = 'assert "<script>" not in html\n    assert "<script>" in html'
    new = 'assert "<script>" not in html\n    assert "<script>" in html'
    content = content[:idx] + new + content[idx + len(old):]
    print('Replacement done!')
else:
    print('Pattern not found!')

with open('agent_access/tests/test_a1_tokens.py', 'w') as f:
    f.write(content)