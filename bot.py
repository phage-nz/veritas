import re
import logging
import discord
import yaml
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("veritas")

URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)

_TWITTER_HOSTS = frozenset({"twitter.com", "x.com"})
_TELEGRAM_HOSTS = frozenset({"t.me", "telegram.me", "telegram.dog"})


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def _extract_urls(text: str) -> list[str]:
    return [url.rstrip(".,;:!?)") for url in URL_PATTERN.findall(text)]


def _get_domain(url: str) -> str:
    return _strip_www(urlparse(url).netloc.lower())


def _get_social_account(url: str, hosts: frozenset[str]) -> str | None:
    parsed = urlparse(url)
    if _strip_www(parsed.netloc.lower()) in hosts:
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            return parts[0].lower()
    return None


def _build_sets(config: dict, list_key: str) -> tuple[set[str], set[str], set[str]]:
    section = config.get(list_key, {})
    domains = {d.strip().lower().rstrip("/") for d in section.get("domains", [])}
    twitter = {a.strip().lower() for a in section.get("twitter", [])}
    telegram = {a.strip().lower() for a in section.get("telegram", [])}
    return domains, twitter, telegram


def _match_url(
    url: str,
    domains: set[str],
    twitter_accounts: set[str],
    telegram_accounts: set[str],
) -> str | None:
    domain = _get_domain(url)
    if domain in domains:
        return domain

    twitter = _get_social_account(url, _TWITTER_HOSTS)
    if twitter and twitter in twitter_accounts:
        return f"@{twitter} (Twitter/X)"

    telegram = _get_social_account(url, _TELEGRAM_HOSTS)
    if telegram and telegram in telegram_accounts:
        return f"@{telegram} (Telegram)"

    return None


def _check_urls(
    urls: list[str],
    block_sets: tuple[set[str], set[str], set[str]],
    warn_sets: tuple[set[str], set[str], set[str]],
) -> dict[str, list[str]]:
    blocked: list[str] = []
    warned: list[str] = []

    for url in urls:
        block_match = _match_url(url, *block_sets)
        if block_match:
            if block_match not in blocked:
                blocked.append(block_match)
            continue

        warn_match = _match_url(url, *warn_sets)
        if warn_match and warn_match not in warned:
            warned.append(warn_match)

    return {"block": blocked, "warn": warned}


class VeritasBot(discord.Client):
    def __init__(self, config: dict) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.monitored_channels: set[int] = set(config.get("channels", []))
        self.block_sets = _build_sets(config, "blocklist")
        self.warn_sets = _build_sets(config, "warnlist")

    async def on_ready(self) -> None:
        log.info("Veritas ready: %s (ID %s)", self.user, self.user.id)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.channel.id not in self.monitored_channels:
            return

        urls = _extract_urls(message.content)
        if not urls:
            return

        matches = _check_urls(urls, self.block_sets, self.warn_sets)

        if matches["block"]:
            try:
                await message.delete()
            except discord.Forbidden:
                log.warning(
                    "Missing Manage Messages permission in channel %s",
                    message.channel.id,
                )
                return
            except discord.NotFound:
                return

            sources = "\n".join(f"• {name}" for name in matches["block"])
            try:
                await message.author.send(
                    f"Your message in **#{message.channel.name}** was removed.\n\n"
                    f"It contained a link to the following source(s) that are not permitted:\n{sources}"
                )
            except discord.Forbidden:
                log.info(
                    "Could not DM %s — DMs are disabled or the user has blocked the bot",
                    message.author,
                )
            return

        if matches["warn"]:
            sources = "\n".join(f"• {name}" for name in matches["warn"])
            try:
                await message.add_reaction("🚩")
            except discord.HTTPException as exc:
                log.error(
                    "Failed to add reaction in channel %s: %s", message.channel.id, exc
                )
            try:
                await message.reply(
                    f"⚠️ This message links to the following source(s) of low reputation:\n{sources}\n\n"
                    "Treat with caution and verify independently before acting on or sharing.",
                    mention_author=False,
                )
            except discord.HTTPException as exc:
                log.error(
                    "Failed to send warning reply in channel %s: %s",
                    message.channel.id,
                    exc,
                )


def main() -> None:
    config = load_config()
    token = config.get("token")
    if not token:
        raise ValueError("Bot token not set in config.yaml")
    bot = VeritasBot(config)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
