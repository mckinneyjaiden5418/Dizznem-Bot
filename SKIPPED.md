# Maintenance Sweep — Skipped Items

Found during the `chore/maintenance-sweep` pass but not touched, because each one
was either outside the whitelist, ambiguous, or required a judgment call the
whitelist explicitly said to skip rather than make. Ranked by apparent severity.
No action needed to receive this — it's a backlog, not a task list.

## 1. Unguarded dict-key access on external (yt-dlp) data — youtube.py

**File:lines:** `python/bot/cogs/misc/youtube.py:279, 391, 400, 571, 586, 633`

Six spots build a "Now Playing" / queue embed via `self.current['title']`,
`info['title']`, `item['title']` (and matching `'webpage_url'` accesses) with
direct bracket indexing, not `.get()`. If yt-dlp ever returns an info dict
missing one of those keys (malformed/private/deleted video metadata), this
raises an unguarded `KeyError`.

**Why skipped:** this isn't classic user-input validation (it's external API
response data), and the whitelist's category 5 explicitly forbids adding
default values/coercion as the fix — so swapping to `.get("title", "Unknown")`
would violate the same rule that would justify touching it. A category-5-
compliant fix (early-return guard, no defaults) doesn't have an obvious shape
inside an embed-building loop over multiple queue items. Also, `youtube.py` is
already being modified by a separate in-flight PR this session
(`fix/youtube-playback-errors`), so touching it again here risks compounding
merge conflicts for something that needs a real design decision, not a
mechanical fix.

## 2. `interaction.response.send_message` error formatting is genuinely mixed, not dominant

**Files:** `python/utils/money/stock_views.py` (7 call sites), `python/utils/money/store_views.py` (2 ownership-check call sites, but its own `_insufficient_funds` helper uses Embed), `python/bot/cogs/misc/games.py:71-86` (3 call sites)

Command-level errors (`ctx.send`) consistently use `Embed(title="Error", color=Color.red())` throughout the repo, so that pattern was safe to align to (see `[category 4]` commits below). But interaction-based errors (button/modal `interaction.response.send_message`) are a genuine mix: most are plain text, but `StoreView._insufficient_funds` deliberately uses a richer `❌ Insufficient Funds` embed. There's no single dominant format for this specific call type to align to.

I actually made this mistake once during the sweep — converted `stock_views.py`'s `AmountModal.on_submit` to Embed, then caught that it made the file *less* internally consistent (2 Embed vs. 7 remaining plain-text calls in the same file), and reverted it (see the revert commit below). Standardizing this properly is a real design decision (pick one format for interaction errors and migrate all ~12 call sites together) — not a mechanical align-to-existing-pattern fix, so it's out of scope for this whitelist.

## 3. `# noqa: F401` logger imports — not actually dead code

**Files:lines:** `python/bot/cogs/_template.py:5`, `python/bot/cogs/money/money_making.py:10`, `python/bot/cogs/money/money.py:8`, `python/bot/cogs/misc/admin.py:12`, `python/bot/cogs/misc/user_info.py:6`

`from log import logger` with no other use of `logger` in the file, `# noqa: F401` suppressing the unused-import lint warning. Looked like dead-code candidates at first, but `_template.py`'s copy has an explicit comment: `# noqa: F401 -- Import logger for possible use.` This is a deliberate, repo-wide boilerplate convention (every new cog gets a ready-to-use logger import via the template), not an accidental unused import. Category 2 requires "provably unreferenced" with no ambiguity — this has clear evidence of intentionality, so it's a skip, not a removal.

## 4. Vaulted pride-month trigger — intentionally commented out

**File:line:** `python/bot/bot.py:202`

```python
# ("gay", "Dizznem Bot is an LGBTQ+ ally!"),  # Vaulted pride month command
```

Commented-out code, which is category 2's territory on its face -- but the
inline "Vaulted" annotation plus the CHANGELOG history (pride-month response
commands were explicitly added in 2.2.0 and removed in 2.2.1, on a seasonal
cadence) both indicate this is a deliberate archive for reactivation, not
forgotten cruft. Skipped.

---

**Everything else** in the seven whitelist categories was either already
clean (ruff already enforces unused-import/unused-variable removal on this
repo by default, even with no `ruff.toml` present on `main`, so category 2's
low-hanging fruit was already covered before this sweep started) or is listed
above.
