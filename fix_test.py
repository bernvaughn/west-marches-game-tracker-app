with open('agent_access/tests/test_a1_tokens.py', 'r') as f:
    content = f.read()

# The test has:
#     assert "<script>" not in html
#     assert "<script>" in html
#
# It should be:
#     assert "<script>" not in html
#     assert "<script>" in html
#
# The second assertion should check for the escaped version that Django outputs

content = content.replace(
    'assert "<script>" not in html\n    assert "<script>" in html',
    'assert "<script>" not in html\n    assert "<script>" in html'
)

with open('agent_access/tests/test_a1_tokens.py', 'w') as f:
    f.write(content)

print('Fixed!')