import os
import tweepy
from atproto import Client
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import re
import requests
import tempfile
from urllib.parse import urlparse

# .env dosyasından çevresel değişkenleri yükle
load_dotenv()

# Twitter API kimlik bilgileri
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_Barer_TOKEN')
TWITTER_USERNAME = os.getenv('TWITTER_USERNAME')

# Bluesky kimlik bilgileri
BLUESKY_EMAIL = os.getenv('BLUESKY_EMAIL')
BLUESKY_PASSWORD = os.getenv('BLUESKY_PASSWORD')

# Son tweet ID'sini saklamak için dosya
LAST_TWEET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'last_tweet_id.txt')

def get_last_tweet_id():
    """Son işlenen tweet ID'sini dosyadan okur"""
    try:
        with open(LAST_TWEET_FILE, 'r') as f:
            tweet_id = f.read().strip()
            print(f"last_tweet_id: {tweet_id}")
            return int(tweet_id) if tweet_id else None
    except FileNotFoundError:
        print("last_tweet_id dosyası bulunamadı")
        return None

def save_last_tweet_id(tweet_id):
    """Son işlenen tweet ID'sini dosyaya kaydeder"""
    with open(LAST_TWEET_FILE, 'w') as f:
        f.write(str(tweet_id))

def setup_twitter_client():
    """Twitter API v2 istemcisini yapılandırır"""
    client = tweepy.Client(
        bearer_token=TWITTER_BEARER_TOKEN,
        wait_on_rate_limit=False
    )
    return client

def setup_bluesky_client():
    """Bluesky API istemcisini yapılandırır"""
    client = Client()
    client.login(BLUESKY_EMAIL, BLUESKY_PASSWORD)
    return client

def clean_tweet_text(text):
    """Tweet metninden referans linklerini ve gereksiz boşlukları temizler"""
    # Twitter referans linklerini kaldır
    text = re.sub(r'https://t\.co/\w+', '', text)
    # Birden fazla boşluğu tek boşluğa indir
    text = re.sub(r'\s+', ' ', text)
    # Baştaki ve sondaki boşlukları temizle
    return text.strip()

def is_original_tweet(tweet):
    """Tweet'in orijinal tweet olup olmadığını kontrol eder"""
    # Eğer tweet'in referans verdiği başka bir tweet varsa, bu bir yanıt veya retweet'tir
    return not hasattr(tweet, 'referenced_tweets') or not tweet.referenced_tweets

def download_media(url):
    """Medya dosyasını indirir ve geçici bir dosyaya kaydeder"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Dosya uzantısını belirle
        content_type = response.headers.get('content-type', '')
        if 'image/jpeg' in content_type:
            ext = '.jpg'
        elif 'image/png' in content_type:
            ext = '.png'
        elif 'image/gif' in content_type:
            ext = '.gif'
        else:
            ext = '.jpg'  # Varsayılan
        
        # Geçici dosya oluştur
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        
        # Dosyayı kaydet
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)
        
        temp_file.close()
        return temp_file.name
    except Exception as e:
        print(f"Medya indirme hatası: {e}")
        return None

def get_new_tweets(client, last_tweet_id):
    """Son tweet'ten sonraki yeni tweet'leri alır"""
    tweets = []
    try:
        # Önce kullanıcı ID'sini al
        user = client.get_user(username=TWITTER_USERNAME)
        if not user.data:
            print(f"Kullanıcı bulunamadı: {TWITTER_USERNAME}")
            return tweets

        # Kullanıcının tweet'lerini al
        user_tweets = client.get_users_tweets(
            user.data.id,
            exclude=['retweets', 'replies'],
            tweet_fields=['created_at', 'text', 'referenced_tweets', 'attachments'],
            expansions=['attachments.media_keys'],
            media_fields=['url', 'preview_image_url', 'type']
        )

        if user_tweets.data:
            # Medya bilgilerini bir sözlüğe kaydet
            media_dict = {}
            if hasattr(user_tweets, 'includes') and 'media' in user_tweets.includes:
                for media in user_tweets.includes['media']:
                    if hasattr(media, 'media_key') and hasattr(media, 'url'):
                        media_dict[media.media_key] = media.url

            for tweet in user_tweets.data:
                tweet_id = int(tweet.id)
                # Sadece last_tweet_id'den büyük olan tweet'leri al
                if last_tweet_id and tweet_id <= last_tweet_id:
                    print(f"last_tweet_id'den küçük tweet: {tweet_id}")
                    continue
                else:
                    print(f"last_tweet_id'den büyük tweet: {tweet_id}")
                    
                # Sadece orijinal tweet'leri al
                if is_original_tweet(tweet):
                    # Tweet metnini temizle
                    clean_text = clean_tweet_text(tweet.text)
                    if clean_text:  # Boş tweet'leri atla
                        tweet_data = {
                            'id': tweet_id,
                            'text': clean_text,
                            'created_at': tweet.created_at,
                            'media_urls': []
                        }
                        
                        # Tweet'te medya varsa URL'lerini ekle
                        if (hasattr(tweet, 'attachments') and 
                            tweet.attachments is not None and 
                            'media_keys' in tweet.attachments and 
                            tweet.attachments['media_keys'] is not None):
                            for media_key in tweet.attachments['media_keys']:
                                if media_key in media_dict:
                                    tweet_data['media_urls'].append(media_dict[media_key])
                        
                        tweets.append(tweet_data)
    except tweepy.errors.Forbidden as e:
        print(f"Twitter API erişim hatası: {e}")
    except Exception as e:
        print(f"Beklenmeyen hata: {e}")
    
    return tweets

def post_to_bluesky(client, text, media_urls=None):
    """Tweet'i Bluesky'ye gönderir"""
    try:
        # Medya dosyalarını indir ve yükle
        uploaded_images = []
        if media_urls:
            for url in media_urls:
                media_path = download_media(url)
                if media_path:
                    try:
                        # Bluesky'ye medyayı yükle
                        with open(media_path, 'rb') as f:
                            upload = client.upload_blob(f)
                            # BlobRef nesnesini doğru şekilde al
                            if hasattr(upload, 'blob'):
                                uploaded_images.append(upload.blob)
                            else:
                                print(f"Medya yükleme hatası: BlobRef nesnesi bulunamadı")
                    finally:
                        # Geçici dosyayı temizle
                        if os.path.exists(media_path):
                            os.unlink(media_path)
        
        # Tweet'i medya ile birlikte gönder
        if uploaded_images:
            # Bluesky API'si için medya ekleme
            embed = {
                "$type": "app.bsky.embed.images",
                "images": [{"alt": "Image", "image": img} for img in uploaded_images]
            }
            client.send_post(text, embed=embed)
        else:
            client.send_post(text)
        return True
    except Exception as e:
        print(f"Bluesky gönderim hatası: {e}")
        return False

def main():
    # API istemcilerini yapılandır
    twitter_client = setup_twitter_client()
    bluesky_client = setup_bluesky_client()
    
    # Son işlenen tweet ID'sini al
    last_tweet_id = get_last_tweet_id()
    
    # Yeni tweet'leri al
    new_tweets = get_new_tweets(twitter_client, last_tweet_id)
    
    # Tweet'leri ters sırayla işle (eskiden yeniye)
    for tweet in reversed(new_tweets):
        # Tweet'i Bluesky'ye gönder
        if post_to_bluesky(bluesky_client, tweet['text'], tweet.get('media_urls')):
            # Başarılı gönderimden sonra son tweet ID'sini güncelle
            save_last_tweet_id(tweet['id'])
            print(f"Tweet başarıyla gönderildi: {tweet['text'][:50]}...")
            if tweet.get('media_urls'):
                print(f"Medya sayısı: {len(tweet['media_urls'])}")

if __name__ == "__main__":
    main() 
