import os
import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from flask import Flask
from threading import Thread
import asyncio

# === CONFIGURATION ===
TOKEN = os.environ['DISCORD_TOKEN']
CHANNEL_ID = 1399361038159314965
ROLE_ID = 1399455555793326211
KEYWORDS = [
    "messi", "ronaldo", "mbappé", "neymar", "barça", "real", "psg",
    "transfert", "prêt", "premier league", "ligue 1", "liga", "serie a",
    "bundesliga", "europa", "champions", "inter", "naples", "de bruyne",
    "bellingham", "griezmann", "haaland"
]
POSTED_FILE = "posted.json"

# === CHARGEMENT DES ARTICLES DÉJÀ POSTÉS ===
def load_posted_articles():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_posted_articles(posted):
    with open(POSTED_FILE, "w") as f:
        json.dump(list(posted), f)

posted_articles = load_posted_articles()

# === DISCORD BOT ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# === STATUT DU BOT ===
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Streaming(
        name="Foot Mercato 🔥",
        url="https://twitch.tv/lecazinolive"
    ))
    print(f"{bot.user} est en ligne !")

# === SCRAPING FOOTMERCATO ===
def scrape_articles():
    url = "https://www.footmercato.net/"
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        articles = soup.find_all('article', limit=6)

        new_posts = []

        for article in articles:
            title_tag = article.find('h2')
            title = title_tag.text.strip() if title_tag else "Sans titre"

            link_tag = article.find('a', href=True)
            link = link_tag['href'] if link_tag else None
            if link and not link.startswith('http'):
                link = "https://www.footmercato.net" + link

            if not link or link in posted_articles:
                continue

            title_lower = title.lower()
            if not any(keyword in title_lower for keyword in KEYWORDS):
                continue

            # Scrap contenu article
            article_res = requests.get(link)
            article_soup = BeautifulSoup(article_res.text, 'html.parser')

            # Résumé (sous le titre)
            summary_tag = article_soup.find('h2')
            summary = summary_tag.text.strip() if summary_tag else ""

            # Texte complet
            paragraphs = article_soup.find_all('p')
            full_text = "\n\n".join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20)

            if not full_text:
                continue

            img_tag = article_soup.find('img')
            img_url = img_tag['src'] if img_tag and 'src' in img_tag.attrs else None

            new_posts.append({
                'title': title,
                'link': link,
                'summary': summary,
                'text': full_text,
                'image': img_url
            })

        return new_posts

    except Exception as e:
        print(f"[ERREUR SCRAPING] {e}")
        return []

# === BOUCLE DE PUBLICATION ===
@tasks.loop(minutes=10)
async def news_loop():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print("[ERREUR] Salon introuvable.")
        return

    posts = scrape_articles()
    for post in posts:
        posted_articles.add(post['link'])
        save_posted_articles(posted_articles)

        # Préparer le texte complet avec mention rôle + réseaux
        role_mention = f"<@&{ROLE_ID}>"
        summary = post['summary']
        full_text = post['text']
        footer_text = (
            "\n\n---\n"
            "📢 **Suis-nous sur les réseaux !**\n"
            "▶️ YouTube : https://youtube.com/@le_casino?si=fJrkRI_R_cvjT1HS\n"
            "🎵 TikTok : https://www.tiktok.com/@lcn1modz?is_from_webapp=1&sender_device=pc\n"
            "🛒 Ma boutique : https://payhip.com/Lecasino"
        )

        description = f"{role_mention}\n\n**{summary}**\n\n{full_text}{footer_text}"

        embed = discord.Embed(
            title=post['title'],
            description=description[:4096],  # Limite pour le embed
            color=0x2F3136
        )

        if post['image']:
            embed.set_image(url=post['image'])

        now = datetime.now().strftime("%d/%m/%Y à %H:%M")
        embed.set_footer(text=f"🕓 Publié le {now}")
        embed.add_field(name="🔗 Consulter l'article", value=f"[Clique ici]({post['link']})", inline=False)

        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"[ERREUR ENVOI EMBED] {e}")

# === FLASK POUR UPTIME ROBOT ===
app = Flask('')

@app.route('/')
def home():
    return "Bot actif."

def run():
    port = int(os.environ.get("PORT", 8080))  # Prend le port donné par Render sinon 8080
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# === LANCEMENT ===
if __name__ == "__main__":
    keep_alive()

    async def main():
        async with bot:
            news_loop.start()
            await bot.start(TOKEN)

    asyncio.run(main())
