"""Prompt assembly for Epic 06 (AI Creative Generation).

Brand-Aware Generation: every prompt below is grounded in the company's
brand profile (Epic 03) and, when available, the synthesized brand context
(Epic 05) - colors, logo, tone, typography, visual style and product
information all flow into both the image prompt and the copy prompt.
"""

CREATIVE_TYPE_GUIDANCE = {
    'instagram_post': 'A square (1:1) Instagram feed post.',
    'facebook_post': 'A landscape (1.91:1) Facebook feed post.',
    'linkedin_post': 'A professional, landscape LinkedIn feed post.',
    'carousel': 'The first slide of a square (1:1) Instagram/Facebook carousel.',
    'story': 'A vertical (9:16) Instagram/Facebook Story.',
    'promotional_creative': 'A promotional/sale creative, square format.',
    'festival_creative': 'A festival/seasonal greeting creative, square format.',
    'product_creative': 'A product-focused creative showcasing the product clearly, square format.',
}


def _joined(values, empty='not specified'):
    return ', '.join(v for v in values if v) or empty


def _brand_lines(brand_profile):
    if brand_profile is None:
        return ['Brand guidelines: not specified.']
    colors = ', '.join(f'{c.get("name", "")} {c.get("hex", "")}'.strip() for c in brand_profile.brand_colors) or 'not specified'
    return [
        f'Brand colors: {colors}',
        f'Brand tone: {brand_profile.tone or "not specified"}',
        f'Visual style: {brand_profile.visual_style or "not specified"}',
        f'Typography notes: {brand_profile.typography_notes or "not specified"}',
        f"Do's: {_joined(brand_profile.dos)}",
        f"Don'ts: {_joined(brand_profile.donts)}",
    ]


def build_image_prompt(company, brand_profile, creative_type, prompt_brief, product_info, variation_number):
    format_guidance = CREATIVE_TYPE_GUIDANCE.get(creative_type, 'A social media creative.')
    lines = [
        f'Create a polished, on-brand marketing creative for "{company.name}" ({company.industry or "general business"}).',
        format_guidance,
        f'Creative brief: {prompt_brief or "Use your best judgement based on the brand context below."}',
        f'Product information: {product_info or _joined(company.products, empty="not specified")}',
        *_brand_lines(brand_profile),
        f'This is variation {variation_number} of 3 - make it visually distinct from the other variations '
        'while staying on-brand.',
        'Do not include any text overlay unless explicitly part of the brief - focus on the visual.',
    ]
    if brand_profile is not None and brand_profile.logo:
        lines.append('A reference image of the brand logo is attached - incorporate it tastefully (e.g. a small corner mark).')
    return '\n'.join(lines)


COPY_SYSTEM_PROMPT = (
    'You are a senior social media copywriter for a digital marketing agency. '
    'Write copy that matches the brand voice/tone exactly and never uses restricted words.'
)


def build_copy_prompt(company, brand_profile, brand_context, creative_type, prompt_brief, product_info):
    format_guidance = CREATIVE_TYPE_GUIDANCE.get(creative_type, 'a social media creative')
    lines = [
        f'Write the copy for {format_guidance} for "{company.name}".',
        f'Creative brief: {prompt_brief or "Use your best judgement."}',
        f'Product information: {product_info or _joined(company.products, empty="not specified")}',
    ]
    if brand_context is not None and brand_context.summary:
        lines += ['', 'Brand context:', brand_context.summary]
    elif brand_profile is not None:
        lines += ['', *_brand_lines(brand_profile)]
    if brand_profile is not None and brand_profile.restricted_words:
        lines.append(f'Restricted words - never use these: {_joined(brand_profile.restricted_words)}')
    return '\n'.join(lines)
