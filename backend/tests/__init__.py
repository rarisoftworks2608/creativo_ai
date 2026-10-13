"""Test package.

Safety net: the tests run Celery tasks inline, and backend/.env holds the real provider keys, so
any test that forgot to mock an AI provider would silently make real (paid) API calls. Blanking
the keys here makes such a test fail with "credentials not configured" instead of spending
money. Tests that exercise a provider class do so against mocked HTTP.
"""

import os

for _key in (
    'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'GROQ_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY',
    'HF_TOKEN', 'CF_ACCOUNT_ID', 'CF_API_TOKEN', 'REPLICATE_API_TOKEN',
):
    os.environ[_key] = ''
