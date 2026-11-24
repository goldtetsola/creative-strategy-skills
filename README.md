# Creative strategy skills

Free creative strategy skills for your AI agent. Give it your ads and your results, and it tells you what creative sells, why buyers respond to it, and what to make next.

Built for creative strategists, and for media buyers who work with creative. Works in Claude Code and Codex, or any agent that can read files and run Python. MIT licensed.

New skills land here over time. Watch the repo or follow me on X at [@gold_tesla](https://x.com/gold_tesla) to hear when I add one.

## The skills

| Skill | What it does |
|---|---|
| `creative-performance-analysis` | Compares the ads that earn spend with the ones that don't, finds the moment or line that makes the difference, and gives blueprints for what to shoot or edit next |

## What you get back

A creative analysis written the way a strategist would talk you through it. Numbers stay in a saved Evidence file underneath, so the read itself stays about creative. This excerpt is from a made-up account:

> **What sells right now is proof the buyer can check for themselves, not a promise they have to trust.**
>
> You can see it in Ad 21. It took almost all the prospecting spend and brought in most of the new customers this fortnight, while Ad 24, with the same bottle, page and ad set, barely spent.
>
> The difference is one moment. 21 pulls the bottle out of a hot car and shakes it so you hear the ice. 24 is a studio shot that writes "Cold for 24 hours" on screen and asks you to trust it.
>
> **1. The same check-it-yourself proof for the food jar.**
> The jar took about a third of the spend this fortnight on "keeps soup hot for 12 hours" written over a product shot, and almost nobody bought. Show someone opening it at their desk at lunch with the steam coming off the soup.

It gives creative moves only. It won't touch budgets, bids, audiences or launch settings, and it gives blueprints, not ad copy or scripts.

## Install

Any agent (Claude Code, Codex, Cursor and others):

```bash
npx skills add goldtetsola/creative-strategy-skills
```

Then ask it what creative is working. A run takes about 5 to 10 minutes. Your agent needs to read files and run Python 3.11 or later.

### Claude Code plugin

```text
/plugin marketplace add goldtetsola/creative-strategy-skills
/plugin install creative-strategy@goldtetsola
```

The plugins add a reading check, which reminds the agent which guides it still has to read before it writes the analysis. New skills arrive with `/plugin update`.

### Codex plugin

```shell
codex plugin marketplace add goldtetsola/creative-strategy-skills
codex plugin add creative-strategy@goldtetsola
```

When Codex asks you to trust the plugin's hook, allow it.

## What to give it

Whatever you have: an Ads Manager export or screenshots, the ad videos and images, and customer reviews. More inputs give a fuller read. With fewer, it says what's missing and what that would answer.

### Video analysis

There's nothing to set up in advance. The first time it needs to look inside a video, it asks before uploading anything to Google's Gemini. If you don't have a Gemini key yet, it opens a small file in your text editor with a link to get a free one. Paste the key, save, and say "done". Your key stays in that file on your computer and never goes into the chat.

If you'd rather set it up now, paste this into your agent:

```text
Set up video analysis for the creative-performance-analysis skill.
```

Each video costs one Gemini API call, on your key.

## Make it sound like you

`references/voice.md` inside the skill sets how the analysis sounds. Edit it to match your own style; the method and evidence rules don't change.

## Work with me

The skills are free. If you'd rather have it done for you:

- **Creative analysis for your brand.** I go through your ads and results and tell you what's working, what isn't, and what to make next.
- **Ad account management.** I run your ad accounts and keep the creative and the spend pulling in the same direction.

DM me on X at [@gold_tesla](https://x.com/gold_tesla).

## Feedback

Found a bug, or a skill that gave bad advice? Open an issue with what you asked and what it did.

## License

MIT. See [LICENSE](LICENSE).
