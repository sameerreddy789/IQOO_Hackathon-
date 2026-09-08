# Pitch Deck

| File | Purpose |
| :--- | :--- |
| `DevContextAI_iQOO_Phase1.pdf` | **Upload this** to the Deck / Document field. 10 slides, 16:9, 1.37 MB (limit is 25 MB). |
| `devcontext-ai-deck.html` | Source. Edit text here and re-render. |

## Re-rendering after an edit

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --headless=new --disable-gpu --no-pdf-header-footer `
  --virtual-time-budget=20000 --run-all-compositor-stages-before-draw `
  "--print-to-pdf=$PWD\deck\DevContextAI_iQOO_Phase1.pdf" `
  "file:///$($PWD -replace '\\','/')/deck/devcontext-ai-deck.html"
```

Or just open the HTML in Chrome and print: destination *Save as PDF*, layout
*Landscape*, margins *None*, **Background graphics on** (without that the dark
theme prints white).

## Slides

| # | Slide | Carries |
| :--- | :--- | :--- |
| 01 | Title | Name, tagline, Track 06, Finale eligibility |
| 02 | The problem | Four pain points, and the "nothing persists" gap |
| 03 | Who this is for | Indian persona: IT-services juniors, tier-2/3 students |
| 04 | How it works | The 5-component flow, colour-coded by execution location |
| 05 | On-device intelligence | 5/5 valid, offline proof, and the 492s latency finding |
| 06 | The artifact | `.devcontext/` tree, `init.sh`, and the security posture |
| 07 | Cross-device bridge | Office Kit clipboard, file transfer, remote control |
| 08 | Honest status | Built vs on-site, with evidence per row |
| 09 | Chennai execution | Red/Green split and checkpoint milestones |
| 10 | The team | Prior builds, and why the hard part is already solved |

## Notes on the content

Slide 05 leads with the 492-second CPU figure rather than hiding it. That number is
the argument for the on-site NPU work, and volunteering it is more credible than
having a judge find it.

Slide 08 exists on purpose. Listing what is not built, with verifiable evidence for
what is, reads better to a technical jury than uniform confidence — and every claim
on it can be checked in the repository.

Slide 04 states the missing backend as a deliberate decision tied to the Red Light
constraint, so the simplicity reads as judgement rather than as a shortcut.

## If a designer wants to restyle it

Design tokens are CSS variables at the top of the HTML (`--bg`, `--panel`, `--cyan`,
`--amber`, and so on). Changing those recolours the whole deck consistently. Icons
are inline SVG, so there are no emoji or image dependencies and nothing to break on
another machine.
