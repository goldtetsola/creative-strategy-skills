# Inspecting ads

The shared way to inspect an ad and explain what the evidence supports. It deconstructs the ad's argument and execution: what it asks the buyer to notice, want, believe and do, and why that may work. A transcript summary, performance ranking or list of framework names is not a creative analysis.

## Results and delivery

For performance questions, identify the period, comparison, outcome definition and benchmark. Verify claims such as dominant spend against the relevant peers or population. Distinguish why an ad gets delivery from why it attracts attention or generates customers; one answer does not establish the others.

Check material eligibility, launch, pause, budget and comparison differences before explaining delivery. Missing, zero and undefined are distinct. Missing outcomes prevent a performance verdict; they do not prevent supported analysis of the argument. A prelaunch or substance-only review needs no invented metrics or account export.

**Low delivery can be evidence.** Where an ad repeatedly earns little spend while comparable peers receive delivery, despite reasonable opportunity, that is a negative signal about its delivery competitiveness in that setting. It does not prove poor acquisition performance, an exact creative cause, or Meta's internal reasoning. This interpretation is industry inference, strengthened by repeated behavior, comparable opportunity, and a relevant, reliable optimization signal.

Check historical eligibility, launch time, objective, timing, constraints, and parent campaign/ad-set delivery. A late launch, rejection, technical issue, or parent that barely delivered can leave opportunity unresolved. Unknown opportunity is different from a verified constraint. Sharing an ad set alone does not establish comparability; reasonable opportunity does not require equal spend or a conversion sample for every ad.

Keep the two outcomes separate:

| Observed pattern | Interpretation |
| --- | --- |
| Strong delivery and supported acquisition success | Study the strengths for expansion; scope success to the measured conditions. |
| Strong delivery and weak acquisition | Preserve promising delivery strengths while investigating conversion weaknesses. |
| Weak delivery despite reasonable opportunity | Investigate the creative contrast; thin acquisition data does not erase the negative delivery signal. |
| Little delivery with a verified constraint or unknown opportunity | State what cannot be judged and why; do not invent creative rejection. |
| Attractive acquisition cost on little spend | Potential acquisition signal, not proof that efficiency survives scale. |

## Inspect the actual creative

Match each asset and version to its complete capture ([video capture](video-capture.md)), full primary texts, headlines, CTA, destination, offer and configured variants. A stable asset ID locates evidence; it does not replace checking the bytes and depth of the capture. Verify current copy and destination separately. Configured options do not establish which combination delivered.

Account for decision-relevant capture details, copy and coverage exceptions. Inspect original media when a consequential ambiguity, timing, delivery or legibility question remains. Name the evidence actually used; capture-only analysis must not claim direct viewing. Missing media limits only details a verified capture cannot establish.

For results or comparisons, apply the [evidence rules](evidence-rules.md#intake-and-transformations). Inspect original rows and nested measures before accepting prepared totals. Preserve IDs, field meanings, population, grain, geography, currency, dates and timezone, attribution, maturity and pagination. Examine every supplied measure and its relationships, including unfamiliar fields and counter-evidence. Present what matters to the question. For buyer wording, apply the [customer-words check](evidence-rules.md#customer-words) before treating a line as customer testimony.

## Inspect the buying argument

After inspecting the actual creative, use these sources to examine the argument. Read the section the question needs before applying it; attaching a framework name after reaching a conclusion is not an analysis.

| Question | Source |
|---|---|
| Buyer entry, structure, identity and register: a felt moment, explanation or aspiration; whether the route fits this purchase | [Complete Creative Strategy (CCS)](ccs.md). Do not invent pain for an identity or Non-Moment route. |
| The main desire, what the buyer knows, and how familiar competing claims are | [Additional Lenses](additional-lenses.md). Desire, awareness and market sophistication are distinct. When the category is crowded or buyers distrust the usual claims, also use the [mature-market response chooser](mature-market-response-chooser.md). |
| Goals, motivations and gain/loss approach | [Mindstates](mindstates.md) is a four-part buyer-psychology model: the goal, one of nine motivations, the feeling sought (Achievement, Autonomy, Belonging, Competence, Empowerment, Engagement, Esteem, Nurturance and Security, each defined in [the motivations table](mindstates.md#the-nine-motivations)), a get-more-good or avoid-more-bad approach, and heuristic cues. Its 18 profiles add feelings to evoke and copy/visual guidance. It explains why an ad's framing may land or mismatch; it does not identify the real buyer's state. To read the feeling an ad is built to prime and how it frames its benefit, as something gained or something avoided, use [reading the appeal](reading-the-appeal.md) with the [gain and loss cues](gain-and-loss-framing.md). |
| Message balance, specificity, clarity, trust, effort, risk and the strength of proof | [Growthcraft](growthcraft.md). Its diagnostic questions are not universal scores or ratios. |

Frameworks do not supply missing customer or product facts. Do not infer a measured buyer state from demographics, an ad name or a persona label, or infer a page fault from an uninspected destination.

## Explain what the evidence supports

For success, distinguish a persuasive strength from a proven reason for the result. Do not assume every element helped because the ad won. For spend, inspect opportunity, allocation, audience mix, auction, timing and measurement as well as creative. Cheap clicks or strong watching alone cannot establish why Meta allocated budget or whether the ad acquired customers.

Challenge material explanations with plausible rivals: talent/production, angle, offer/destination, opportunity, audience, auction, timing/trend, tracking and attribution. Check contrary measures and comparison differences that could change the answer. Keep [platform claims](evidence-rules.md#platform-claims-and-meanings) at their source basis. An invalid comparison is inconclusive; an unresolved cause can still leave a useful creative explanation or hypothesis.

Fractional order credits are not counts of people; preserve the meaning of any figures used.

## Video

Use the video's full capture, read whole, and its copy. Inspect the opening, spoken and visual sequence, proof/demonstration, close, caption/overlay timing, transitions, sound, length and placement-dependent legibility. Note partial endings or uncertainty beside claims that depend on them.

Ask whether the hook promises what the body delivers, whether the viewer can follow the argument, and whether cuts, graphics or captions support or distract from the person, product and proof. Preserve the speaker's connection to the viewer when that connection is the proposed strength. Judge actual execution and buyer effect; editor background is not an explanation. Neither a graphic count nor a prescribed cut interval diagnoses an edit.

### Hook and hold rates

For video performance questions, check **hook rate and hold rate**, alongside spend, clicks and customer results. Definitions are in [the evidence rules](evidence-rules.md#hook-rate) and [CCS](ccs.md#video-attention-definitions). Hold means ThruPlays divided by three-second plays; six-second continuation is a separate measure. Keep other providers' definitions separately named.

For every compared video:

1. Inspect the actual numerator and denominator, exact ad ID and period.
2. If either count is absent and a read-only data route is available, request the source fields named in CCS for that exact ad and period. Record the requested fields and returned counts, omitted field, error or access limit. Do not stop at the first export's column list.
3. Mark each measure **calculated**, **not requested**, **unavailable** or **incompatible**. A valid calculation retains both counts and the source row or file. Unavailable requires an attempted request and its result, or a concrete access limit. Incompatible names the mismatch or invalid denominator.

Calculate only for confirmed videos with matching scope and valid denominators; missing counts are not zero. Quarter/completion counts can add context but cannot substitute for hold.

**Explain the creative meaning, not just the rates.** Hook rate shows how often an impression becomes an early view; hold rates show how many early viewers keep watching. Compare relevant ads or account baselines, then connect the pattern to exact words, visuals, transitions, pacing or proof in the inspected ad. Give the strongest plausible explanation of what draws the audience in, keeps their interest or loses them. Treat audience relevance and resonance as hypotheses supported by the execution and results, not measured feelings or purchase intent. Use no universal high/low cutoffs.

| Relative pattern | Creative and audience interpretation to inspect |
|---|---|
| Strong entry and continuation | The opening attracts attention and the body sustains it. Inspect the promise and payoff that may keep viewers interested; check customer outcomes before calling it a commercial winner. |
| Strong entry, weak continuation | The opening draws people in, but the body may not deliver what they expected or remain relevant. Inspect the promise, transition, clarity, pacing, length and audience fit. |
| Weak entry, strong continuation | The opening may undersell a body that interests those who stay. Inspect whether it makes the topic and value clear soon enough; the remaining viewers are a selected group. |
| Weak entry and continuation | The opening and body may struggle to make the ad relevant or easy to follow. Inspect execution and audience/offer fit alongside tracking and comparison quality; this alone cannot reject the research or entire brief. |

Use a sufficiently detailed retention curve to locate a scene. Completion checkpoints cannot identify an exact second. Compare similar lengths, placements and observation windows. A sharp drop suggests inspection; gradual decline may be ordinary attrition. Inspect the close alongside purchase outcomes: fewer completions do not show that a direct CTA hurts sales. Longer watching is not guaranteed to improve economics.

A hook advantage with similar hold supports an entry advantage, not a large continuation advantage. Absent data permits execution analysis, not an invented retention story.

## Versions and variants

Use this when comparing an ad with a changed version, whether it won, lost or was inconclusive, and when deciding which elements to preserve.

**Match the actual versions.** Link source and variant IDs, actual media and copy revisions, destination/offer, launch dates and primary outcome. Check audience, placements, eligibility, budget, tracking, season and maturity. Do not compare a planned variant with results from another final version. Name the change's purpose when the user or a test record states it: expansion, mechanism isolation or repair. If exposure or comparison quality cannot support the claimed result, the result is **inconclusive**. Visible differences can still support a hypothesis or a better-designed test.

**Map only differences that could matter.** Describe source, variant and possible consequence for relevant dimensions: promise/desire, opening and structure, proof, offer/destination, language/tone/framing, story or explanation sequence. Ask what originally made the argument credible, how the story connected, and whether opposing strengths worked together, such as aspiration and relatability. These are observed qualities and mechanism hypotheses; do not score relatability, psychological alignment, framing ratios or perceived pain. Look for removed context, a weaker reason to believe, lost focus, unnatural performance, changed tone or extra friction. More graphics, benefits or named heuristics do not automatically make an improvement. A new label is not a meaningful new argument.

**Explain and choose the separating move.** Give the observed result, strongest supported explanation or "cause unknown", hypotheses and contrary evidence. Use qualitative confidence with a reason, never canned effect sizes or subjective drift scores. An isolation can keep the same visual or change only copy, duration or a closing beat. An expansion may bundle changes for a useful new treatment; do not claim it isolates one cause. Changing creator, setting and composition can affect human response as well as platform delivery, so improved delivery would not isolate platform classification.
