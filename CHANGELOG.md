# Dizznem Bot Changelog

## [Unreleased]

### Added

- `$summarize` now reads text embedded in messages (titles, descriptions, fields, footers), not just plain content.
- `$retirestock` admin command to pay out and clear a stock's holders before its ticker is changed.

### Fixed

- ABA/Rogue trivia now shows the correct answer even when your guess is marked correct.

### Fixed

- `$aba` / `$roguelineage` no longer show "Message could not be loaded" (loading embed is edited in place instead of deleted).

### Changed

- ABA/Rogue trivia re-rolls entries with no wiki image instead of asking an unanswerable question.
- Added automated coverage for general command helpers and DeepSeek AI request handling.

## [2.2.1] - 2026-7-1

### Removed

- Pride month exclusive response commands.

## [2.2.0] - 2026-6-1

### Added

- New admin commands.
    - $addmoney (adds money to a user).
    - $resetcooldown (resets cooldowns, e.g. $daily and $weekly).
- New and old response commands for pride month.
- $sus command.
    - $sus @{user} to use on someone else.
    - $sus with no @ will do yourself.
- $summarize command.
    - Summarizes the last X messages in a channel using AI.
    - Optional count argument (range 10-50, default 50, max 50).

### Changed

- Balance embed to look better.
- Formatting of AI cooldown / cap messages.
- Level presentation for both $level and $profile.

### Fixed

- $setmoney formatting (admin command).
- Prestige price not scaling.

## [2.1.1] - 2026-5-12

### Added

- Per-user cooldown on AI chat to prevent spam.
- Global semaphore limiting concurrent AI API calls to 3.
    - In other words only 3 AI calls can be made at once, the rest waits in a queue.
- Prompt length cap of 1000 characters for AI chat.

## [2.1.0] - 2026-5-8

### Added

- AI caching.
    - Dizznem Bot AI now remembers the last 10 messages in a conversation for better context.
- Notification for leveling up.
    - Sends in channel if able.
    - Sends in DMs if not able to send in channel.
    - Sends nowhere otherwise but this probably won't happen.

### Changed

- $aba / $roguelineage refactored (ABA April update -- happy April 38th).
    - New nicknames.
    - More lenient answers (i.e. "Goku Blac" instead of "Goku Black" would work since that is close enough)
    - Now parses the wiki automatically, so new characters/races/artifacts/creatures are picked up without manual updates.
        - Occasionally an unintended entry may appear as a question. If this happens, let me know and I'll filter it out.

### Fixed

- $daily and $weekly money amount not being bolded.
- $setmoney (admin command) text being misleading / not accurate.
- YouTube feature should work WAYYYYYY better now (i.e. not slow... I hope).
    - (It speeds up randomly because it has "Made in Heaven" might patch this in the future idk).

## [2.0.1] - 2026-4-7

### Changed

- Lowered gambling cd to 3 seconds.
- Cooldowns are now formatted by days -> hours -> minutes -> seconds.

### Fixed

- Gambling all your money sometimes not working.
- YouTube command being slow/buggy (probably not but I might have! it's hard to test because the raspberry pi seems like the main reason it was doing this).


## [2.0.0] - 2026-3-29

### Added

- Whole new/refactored backend!
- Dizznem Bot now has a YouTube feature!
    - $play "video title" to play a video
    - Alternatively, you can do $play (video link)
    - $skip to skip a video.
    - $pause to pause a video.
    - $resume to resume a paused video.
    - $stop stops the playback, clears the queue, and disconnects.
    - $queue shows the queue.
    - $nowplaying shows what is currently playing.
    - See notes section in changelog for more information about this feature.
- New response commands.
- There was another big feature I had 95% complete but apparently I have to wait over a week to get it approved so that's coming in a later update.
- Some other things that I just don't feel like typing out go figure it out yourself.

### Changed

- All output replaced with embeds with small exceptions such as AI responses.
- New XP formula.
- The way some cooldowns work.
- $give/transfer maximum transfer amount increased to $5,000,000.
- $weekly now gives you a random amount of money and has been nerfed, but scales with prestige now.
- Stock market overhaul
    - Stocks now point to real life stocks (no more +200% days for Subaru sorry).
        - If you find out what stock each stock is associated with I'll give you a reward.
    - You can only buy whole shares, might change in the future, currently undecided.
    - To buy/sell stocks do $buystock {stock_name} or $sellstock {stock_name}.
    - I'll be able to add more stocks in the future very easily due to this overhaul, so yay!
    - Some other changes I don't feel like typing out just check it out, the rest is self explanatory.
- Dizznem Bot AI slight changes to personality.
- $profile & $level show more information.
- All leaderboard commands condensed to just $leaderboard with a dropdown option to see different leaderboards.
- $store has a more GUI like approach.

### Fixed

- Possible sources of data loss.

### Removed

- All data reset except for...
    - Level related data.
    - $inspiration database.
    - $count database.
- Marvel Rivals tracker ($tracker).
    - May get re-added in the future -- would've delayed release.
- Register command ($register).
    - Not needed anymore.

### Notes

- Your level will start at 1. If you had a lot of messages on Dizznem Bot 1.0.0, you may level up rapidly for a bit until the bot syncs you to the correct level.
- User data that was not reset dates back to 11/21/25.
- YouTube feature will likely have quite a few bugs due to limited testing. Report any bugs to me and I'll work on fixing them.
- YouTube feature will get more refined in a future update (such as vote skipping), I just wanted to get the feature out for 2.0.0.
- YouTube feature probably has a bug where it'll stop playing something randomly, but I wanted to get this out today so I'll fix this later haha.

## [1.0.0] - 2025-3-30

### Added

- Original Dizznem Bot release!
