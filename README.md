# Twitter'dan Bluesky'a Otomatik Paylaşım

Bu script, Twitter hesabınızdaki yeni tweet'leri otomatik olarak Bluesky hesabınıza aktarır.

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. `.env.example` dosyasını `.env` olarak kopyalayın ve gerekli bilgileri doldurun:
```bash
cp .env.example .env
```

3. `.env` dosyasını düzenleyerek Twitter ve Bluesky kimlik bilgilerinizi girin.

## Crontab Ayarı

Script'i düzenli olarak çalıştırmak için crontab'a ekleyin:

```bash
crontab -e
```

Aşağıdaki satırı ekleyin (örneğin her 5 dakikada bir çalıştırmak için):

```
*/5 * * * * cd /root/python/Bluesky && /usr/bin/python3 twitter_to_bluesky.py >> /root/python/Bluesky/cron.log 2>&1
```

## Önemli Notlar

- Script sadece orijinal tweet'leri aktarır (reply'ları aktarmaz)
- Her çalıştığında son işlenen tweet'ten sonraki yeni tweet'leri kontrol eder
- Hata durumunda log dosyasına kayıt düşer 
