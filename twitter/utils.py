from urllib.parse import quote_plus

def build_twitter_search_query(
    keywords=None,
    from_user=None,
    to_user=None,
    mention=None,
    hashtags=None,
    filter_images=False,
    filter_videos=False,
    since=None,      # формат 'YYYY-MM-DD'
    until=None,      # формат 'YYYY-MM-DD'
    lang=None,
    exact=None,
    mode='top'       # 'top' (по умолчанию) или 'latest'
):
    """
    mode: 'top' — сортировка по популярности (как в Twitter при обычном поиске)
          'latest' — сортировка по времени (новые сверху)
    """
    parts = []

    if keywords:
        if isinstance(keywords, list):
            parts.append(" ".join(keywords))
        else:
            parts.append(str(keywords))
    if exact:
        parts.append(f'"{exact}"')
    if from_user:
        parts.append(f"from:{from_user}")
    if to_user:
        parts.append(f"to:{to_user}")
    if mention:
        parts.append(f"@{mention}")
    if hashtags:
        for tag in hashtags:
            parts.append(f"#{tag}")
    if filter_images:
        parts.append("filter:images")
    if filter_videos:
        parts.append("filter:videos")
    if since:
        parts.append(f"since:{since}")
    if until:
        parts.append(f"until:{until}")
    if lang:
        parts.append(f"lang:{lang}")

    query = " ".join(parts)
    url = f"https://twitter.com/search?q={quote_plus(query)}"
    if mode == 'latest':
        url += "&f=live"

    return url, query
