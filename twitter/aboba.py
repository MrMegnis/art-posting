import os
import time
import json
import random
import requests
from utils import build_twitter_search_query
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

COOKIES_FILE = "twitter_cookies.json"
TWITTER_URL = "https://twitter.com"
RESULTS_FILE = "raiden_images.txt"
META_FILE = "raiden_images_with_meta.json"


def get_driver(headless=True):
    options = uc.ChromeOptions()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    return uc.Chrome(options=options, use_subprocess=True)


def load_cookies(driver, cookies_file=COOKIES_FILE):
    if os.path.exists(cookies_file):
        driver.get(TWITTER_URL)
        with open(cookies_file, "r") as f:
            cookies = json.load(f)
        for cookie in cookies:
            if 'sameSite' in cookie:
                cookie.pop('sameSite')
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass


def save_cookies(driver, cookies_file=COOKIES_FILE):
    cookies = driver.get_cookies()
    with open(cookies_file, "w") as f:
        json.dump(cookies, f)
    print("Cookies сохранены!")


def cookies_valid(driver, url):
    driver.get(url)
    time.sleep(4 + random.random() * 2)
    imgs = driver.find_elements(By.XPATH, "//img[contains(@src, 'twimg.com/media')]")
    return len(imgs) > 0


def to_fullsize(url):
    if "name=" in url:
        return url.split("name=")[0] + "name=orig"
    return url


def scroll_and_collect_imgs(driver, with_meta=False, min_scrolls=100, max_scrolls=150, max_images=10_000, min_pause=1.5, max_pause=3.0):
    num_scrolls = random.randint(min_scrolls, max_scrolls)
    print(f"Скроллим страницу {num_scrolls} раз (случайно), чтобы Twitter не заподозрил бота...")
    img_urls = set()
    meta_data = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    for i in range(num_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(min_pause, max_pause))
        tweets = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
        for tw in tweets:
            try:
                imgs = tw.find_elements(By.XPATH, ".//img[contains(@src, 'twimg.com/media')]")
                if not imgs:
                    continue
                urls = [to_fullsize(img.get_attribute("src")) for img in imgs if img.get_attribute("src")]
                for url in urls:
                    img_urls.add(url)
                if with_meta:
                    tweet_data = {}
                    tweet_data['images'] = urls
                    try:
                        user_link = tw.find_element(By.XPATH, ".//a[contains(@href, '/status/')]")
                        user_href = user_link.get_attribute("href")
                        author = user_href.split("/status/")[0].split("/")[-1]
                        tweet_data['author'] = author
                    except Exception:
                        tweet_data['author'] = ""
                    try:
                        tweet_link = tw.find_element(By.XPATH, ".//a[contains(@href, '/status/')]").get_attribute("href")
                        tweet_data['tweet_url'] = tweet_link
                    except Exception:
                        tweet_data['tweet_url'] = ""
                    try:
                        text = tw.find_element(By.XPATH, ".//div[@data-testid='tweetText']").text
                        tweet_data['text'] = text
                    except Exception:
                        tweet_data['text'] = ""
                    try:
                        counters = []
                        spans = tw.find_elements(By.XPATH, ".//div[@role='group']//span")
                        for el in spans:
                            val = el.text.replace(",", "").replace("K", "000").strip()
                            if val.isdigit():
                                counters.append(int(val))
                        tweet_data['replies'] = counters[0] if len(counters) > 0 else 0
                        tweet_data['retweets'] = counters[1] if len(counters) > 1 else 0
                        tweet_data['likes'] = counters[2] if len(counters) > 2 else 0
                        tweet_data['views'] = counters[3] if len(counters) > 3 else 0
                    except Exception:
                        tweet_data['replies'] = tweet_data['retweets'] = tweet_data['likes'] = tweet_data['views'] = 0
                    meta_data.append(tweet_data)
                if max_images and len(img_urls) >= max_images:
                    print(f"Достигнуто ограничение {max_images} артов.")
                    return (img_urls, meta_data) if with_meta else img_urls
            except Exception as e:
                print("Ошибка при парсинге одного твита:", e)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("Достигнут конец ленты.")
            break
        last_height = new_height
        print(f"Собрано {len(img_urls)} уникальных артов и {len(meta_data)} твитов с метаданными...")
        if random.random() < 0.15:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight-500);")
            time.sleep(random.uniform(0.7, 1.2))
    if with_meta:
        return img_urls, meta_data
    return img_urls


def download_images(img_urls, out_dir="raiden_images"):
    os.makedirs(out_dir, exist_ok=True)
    for url in img_urls:
        fname = os.path.join(out_dir, url.split("/")[-1].split("?")[0])
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(fname, "wb") as f:
                    f.write(r.content)
                print(f"Скачано: {fname}")
        except Exception as e:
            print(f"Ошибка при скачивании {url}: {e}")


def main(
    keywords=['Raiden OR "Raiden Shogun" OR 雷電将軍', 'Genshin Impact'],
    exact=None,
    filter_images=True,
    since=None,
    until=None,
    lang=None,
    mode="live",
    headless=True,
    with_meta=True,
    min_scrolls=100,
    max_scrolls=150,
    max_images=10_000,
    min_pause=1.5,
    max_pause=3.0,
    download=False
):
    url, _ = build_twitter_search_query(
        keywords=keywords,
        exact=exact,
        filter_images=filter_images,
        since=since,
        until=until,
        lang=lang,
        mode=mode
    )

    print("Пробуем использовать headless + cookies...")
    try:
        driver = get_driver(headless=headless)
        load_cookies(driver)
        if cookies_valid(driver, url):
            print("Cookies рабочие! Парсим арты...")
            if with_meta:
                img_urls, meta_data = scroll_and_collect_imgs(driver, with_meta=True, min_scrolls=min_scrolls, max_scrolls=max_scrolls, max_images=max_images, min_pause=min_pause, max_pause=max_pause)
                print(f"\nИтого уникальных артов найдено: {len(img_urls)}")
                with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                    for url in img_urls:
                        f.write(url + "\n")
                with open(META_FILE, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, ensure_ascii=False, indent=2)
                print(f"Все метаданные сохранены в {META_FILE}")
            else:
                img_urls = scroll_and_collect_imgs(driver, with_meta=False, min_scrolls=min_scrolls, max_scrolls=max_scrolls, max_images=max_images, min_pause=min_pause, max_pause=max_pause)
                print(f"\nИтого уникальных артов найдено: {len(img_urls)}")
                with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                    for url in img_urls:
                        f.write(url + "\n")
            if download and img_urls:
                download_images(img_urls)
            driver.quit()
            return
        driver.quit()
    except Exception as e:
        print(f"Ошибка WebDriver: {e}")

    print("\nCookies не валидны или отсутствуют.")
    print("Открываю обычный браузер для ручного входа в Twitter...")
    driver = get_driver(headless=False)
    driver.get(url)
    input("Выполни вход в Twitter в браузере и нажми Enter здесь...")
    save_cookies(driver)
    print("Скрипт завершён! Перезапусти его — теперь всё будет работать headless.")
    driver.quit()


if __name__ == "__main__":
    main()
