"""Prompt assembly for Epic 07 (AI Video Generation).

Brand-Aware Generation: grounded the same way as Epic 06's image prompts -
brand colors/tone/voice and product information flow into both the script
and each scene's visual prompt.
"""

VIDEO_TYPE_GUIDANCE = {
    'instagram_reel': 'A fast-paced, vertical (9:16) Instagram Reel.',
    'facebook_reel': 'A fast-paced, vertical (9:16) Facebook Reel.',
    'linkedin_video': 'A professional, landscape LinkedIn video.',
    'short_video': 'A short, punchy vertical short-form video.',
    'promotional_video': 'A promotional/sales video.',
    'product_video': 'A product showcase video, highlighting features clearly.',
    'educational_video': 'An educational/how-to video that explains something step by step.',
}

SCRIPT_SYSTEM_PROMPT = (
    'You are a senior video scriptwriter for a digital marketing agency. Break the brief into a '
    'sequence of short scenes, each with a natural spoken narration line and a clear visual '
    'description, matching the brand voice/tone exactly. '
    'Always respond with only the requested JSON output - never ask clarifying questions or add '
    'commentary. Where the brief or brand details are sparse, make reasonable, on-brand assumptions '
    'and proceed rather than asking for more information.'
)


def _joined(values, empty='not specified'):
    return ', '.join(v for v in values if v) or empty


def _brand_lines(brand_profile):
    if brand_profile is None:
        return ['Brand guidelines: not specified.']
    colors = ', '.join(
        f'{c.get("name", "")} {c.get("hex", "")}'.strip() for c in brand_profile.brand_colors
    ) or 'not specified'
    return [
        f'Brand colors: {colors}',
        f'Brand tone: {brand_profile.tone or "not specified"}',
        f'Brand voice: {brand_profile.brand_voice or "not specified"}',
        f"Do's: {_joined(brand_profile.dos)}",
        f"Don'ts: {_joined(brand_profile.donts)}",
    ]


def build_script_prompt(
    company, brand_profile, brand_context, video_type, prompt_brief, product_info, target_duration_seconds,
):
    format_guidance = VIDEO_TYPE_GUIDANCE.get(video_type, 'a short marketing video')
    lines = [
        f'Write a video script for "{company.name}" ({company.industry or "general business"}).',
        format_guidance,
        f'Target total duration: about {target_duration_seconds} seconds.',
        f'Brief: {prompt_brief or "Use your best judgement based on the brand context below."}',
        f'Product information: {product_info or _joined(company.products, empty="not specified")}',
    ]
    if brand_context is not None and brand_context.summary:
        lines += ['', 'Brand context:', brand_context.summary]
    elif brand_profile is not None:
        lines += ['', *_brand_lines(brand_profile)]
    if brand_profile is not None and brand_profile.restricted_words:
        lines.append(f'Restricted words - never use these: {_joined(brand_profile.restricted_words)}')
    lines.append(
        'Break this into 3-8 short scenes. Each scene needs a natural spoken narration line (a sentence or '
        'two, written to be read aloud) and a visual_description of what should be shown on screen. Keep the '
        'sum of all scene durations close to the target duration.'
    )
    return '\n'.join(lines)


def build_scene_image_prompt(company, brand_profile, video_type, visual_description):
    format_guidance = VIDEO_TYPE_GUIDANCE.get(video_type, 'a short marketing video')
    lines = [
        f'Create a single still visual for one scene of {format_guidance} for "{company.name}".',
        f'Scene visual: {visual_description}',
        *_brand_lines(brand_profile),
        'This still frame will be slowly panned/zoomed in the final video - keep the subject '
        'well-centered with room around the edges. Do not include any text overlay.',
    ]
    return '\n'.join(lines)
