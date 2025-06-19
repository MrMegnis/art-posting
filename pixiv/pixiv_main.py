from pixivpy3 import AppPixivAPI
import json
from tqdm import tqdm

def parse_pixiv(query='', tags=None, max_results=50, output_file='pixiv_data.json', refresh_token=''):
    """
    Парсинг Pixiv по refresh_token, запросу и тегам. Сохраняет метаданные в JSON.
    """

    api = AppPixivAPI()
    api.auth(refresh_token=refresh_token)

    result = []
    fetched = 0
    with tqdm(total=max_results, desc="Parsed arts") as pbar:
        while fetched < max_results:
            search_word = ' '.join(tags) if tags else query
            json_result = api.search_illust(search_word, search_target='partial_match_for_tags', offset=fetched)
            if not json_result.illusts:
                break

            for illust in json_result.illusts:
                meta = {
                    'id': illust.id,
                    'title': illust.title,
                    'user_name': illust.user.name,
                    'user_id': illust.user.id,
                    'tags': [t.name for t in illust.tags],
                    'caption': illust.caption,
                    'image_urls': illust.image_urls,
                    'width': illust.width,
                    'height': illust.height,
                    'total_bookmarks': illust.total_bookmarks,
                    'total_view': illust.total_view,
                    'create_date': illust.create_date,
                    'page_count': illust.page_count
                }
                result.append(meta)
                fetched += 1
                pbar.update(1)
                if fetched >= max_results:
                    break

            if not json_result.next_url:
                break

    # Сохраняем в JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(result)} artworks to {output_file}")

if __name__ == "__main__":
    parse_pixiv(tags=["雷電将軍"], max_results=10000, output_file='data/raiden_4770.json', refresh_token='bcUSLH30_xqfPe5VwMkk2nH82JIJig9_q0d6rbCYo5U')
