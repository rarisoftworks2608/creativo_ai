"""Prompt assembly for Epic 05 (AI Content Strategy).

Two prompt builders: one that turns raw Company (Epic 02) + BrandProfile
(Epic 03) data into a brand-context generation request, and one that turns
a stored BrandContext into a planning/strategy generation request for one
of the STRATEGY_KINDS.
"""


def _joined(values, empty='Not specified.'):
    return ', '.join(v for v in values if v) or empty


BRAND_CONTEXT_SYSTEM_PROMPT = (
    'You are a senior brand strategist analyzing a client business for a digital marketing agency. '
    'Base every analysis strictly on the information provided - do not invent facts about the business. '
    'Where information is missing, say so briefly rather than guessing.'
)


def build_brand_context_prompt(company, brand_profile=None):
    lines = [
        f'Company name: {company.name}',
        f'Industry: {company.industry or "Not specified."}',
        f'Description: {company.description or "Not specified."}',
        f'Website: {company.website or "Not specified."}',
        f'Target market: {company.target_market or "Not specified."}',
        f'Target audience: {company.target_audience or "Not specified."}',
        f'Products: {_joined(company.products)}',
        f'Services: {_joined(company.services)}',
        f'USP: {company.usp or "Not specified."}',
        f'Competitors: {_joined(company.competitors)}',
    ]

    if brand_profile is not None:
        lines += [
            '',
            '--- Brand guidelines ---',
            f'Brand voice: {brand_profile.brand_voice or "Not specified."}',
            f'Tone: {brand_profile.tone or "Not specified."}',
            f'Writing style: {brand_profile.writing_style or "Not specified."}',
            f'Visual style: {brand_profile.visual_style or "Not specified."}',
            f"Do's: {_joined(brand_profile.dos)}",
            f"Don'ts: {_joined(brand_profile.donts)}",
            f'Keywords: {_joined(brand_profile.keywords)}',
            f'Restricted words: {_joined(brand_profile.restricted_words)}',
            '',
            '--- Marketing information ---',
            f'Customer personas: {_joined([p.get("name", "") for p in brand_profile.customer_personas])}',
            f'Offers: {_joined(brand_profile.offers)}',
            f'Campaign information: {brand_profile.campaign_information or "Not specified."}',
        ]

    lines.append(
        '\nAnalyze the business, the brand guidelines, the products/services, and the audience separately, '
        'then write a synthesized brand context summary that a copywriter could use to write on-brand content '
        'without any other briefing.'
    )
    return '\n'.join(lines)


STRATEGY_SYSTEM_PROMPT = (
    'You are a senior social media strategist for a digital marketing agency. '
    'Ground every suggestion in the brand context provided - do not suggest anything that '
    'contradicts the brand voice, restricted words, or stated audience.'
)


def build_strategy_prompt(brand_context, instruction, notes=''):
    parts = [
        'Brand context:',
        brand_context.summary or '(No summary available.)',
        '',
        f'Task: {instruction}',
    ]
    if notes:
        parts += ['', f'Additional guidance from the requester: {notes}']
    return '\n'.join(parts)
