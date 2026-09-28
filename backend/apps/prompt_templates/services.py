from .models import PromptTemplate


def create_new_version(template, *, name=None, body=None, user=None):
    """Creates the next version under the same slug (Epic 21: Versioning - Update
    version). Never mutates an existing row in place - old versions stay exactly
    as they were generated, which is the whole point of keeping history.
    """
    latest_version = PromptTemplate.objects.filter(slug=template.slug).order_by('-version').first()
    next_version = (latest_version.version if latest_version else template.version) + 1

    return PromptTemplate.objects.create(
        slug=template.slug,
        category=template.category,
        platform=template.platform,
        creative_type=template.creative_type,
        name=name if name is not None else template.name,
        body=body if body is not None else template.body,
        version=next_version,
        is_active=False,
        created_by=user,
    )


def activate_version(template):
    """Makes `template` the live version for its slug, deactivating every sibling
    (Epic 21: Versioning - Activate/deactivate). Exactly one active row per slug.
    """
    PromptTemplate.objects.filter(slug=template.slug).exclude(pk=template.pk).update(is_active=False)
    template.is_active = True
    template.save(update_fields=['is_active', 'updated_at'])
    return template


def deactivate_version(template):
    template.is_active = False
    template.save(update_fields=['is_active', 'updated_at'])
    return template


def get_active_guidance(category, *, platform=None, creative_type=None):
    """Looks up the active template body for `category`, preferring the most
    specific match: (platform + creative_type) > creative_type only > platform
    only > category-wide. Returns '' when nothing matches - callers append this
    to a prompt only when non-empty, so an unconfigured category is a silent
    no-op rather than an error.
    """
    candidates = PromptTemplate.objects.filter(category=category, is_active=True)

    for platform_filter, creative_type_filter in (
        (platform, creative_type),
        ('', creative_type),
        (platform, ''),
        ('', ''),
    ):
        match = candidates.filter(platform=platform_filter or '', creative_type=creative_type_filter or '').first()
        if match:
            return match.body

    return ''
