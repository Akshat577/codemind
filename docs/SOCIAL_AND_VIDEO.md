# Social post, video script, titles, thumbnail


---

## 1. LinkedIn post (< 800 characters)

My AI code reviewer kept suggesting things my team had already said no to.

So I gave it memory.

CodeMind recalls your team's rules and past review decisions before every review, then saves every accept/reject with the reason.

What changed:
• Rejected suggestions don't come back. It lists what it skipped and why
• It enforces team rules ("money is integer paise") and cites them
• Repeat mistakes get flagged as recurring for that developer
• One "what have you learned?" button summarises the team's review profile

Built with Hindsight agent memory + Groq.

Code: https://github.com/Akshat577/codemind
Article: <ARTICLE_URL>

#AIAgents #AgentMemory #Hindsight #LLM #AI

**First comment (post right after publishing):**
Memory layer: Hindsight by Vectorize → https://github.com/vectorize-io/hindsight

---

## 2. Video script (target ~3 minutes, 1080p, screen + voiceover, face cam if possible)

**0:00–0:30 Intro (face cam)**
"Hi, I'm Akshat. AI code reviewers have one big problem: they forget. Every pull request, they make the same suggestions, including ones your team already rejected. I built CodeMind, a code reviewer that remembers your team, using Hindsight for memory."

**0:30–1:00 Problem (screen)**
- Load the *payments* snippet. Turn memory **OFF**. Click Review.
- "This is a normal AI review. Generic advice. It doesn't know we store money as integer paise, or that all payment calls go through PaymentClient. And tomorrow it'll say exactly the same thing."

**1:00–3:30 Live demo: retain and recall (screen)**
1. Show the *Memory bank* panel with seeded rules. "Our tech lead taught it a few rules. Each one is retained in a Hindsight bank for this team."
2. Turn memory **ON**, Review. Point to the 🧠 lines: "Every suggestion driven by memory cites it. Here's the paise rule, here's the PaymentClient decision." Point to *Memories recalled for this review*.
3. **Reject** one suggestion with a reason ("we don't want this in this module"). **Accept** the float-money one. "Each decision and the reason are retained in Hindsight right away."
4. Load the *refunds* snippet, same author. Review.
   - "The suggestion we rejected is gone. It's listed under *skipped because your team rejected it before*."
   - "The float-money issue is marked *recurring for ravi*, because Hindsight remembered he made the same mistake."
5. Click **What has CodeMind learned about this team?** "This is Hindsight's reflect: a summary of our standards, rejections and each developer's habits. Great for onboarding."
6. Briefly show `app/memory.py`: `recall` before review, `retain` on verdict, tags for author filtering.

**3:30–4:00 Takeaway (face cam)**
"The lesson: don't store what the AI said, store how your team reacted to it. That's what turns a generic reviewer into one that knows your codebase. The code's on GitHub, and it's built on Hindsight. Links are in the description."

**YouTube description**
CodeMind: an AI code reviewer with long-term memory. It recalls your team's rules and past review decisions and learns from every accept/reject.
Code: https://github.com/Akshat577/codemind
Hindsight: https://github.com/vectorize-io/hindsight
Docs: https://hindsight.vectorize.io/
Agent memory: https://vectorize.io/what-is-agent-memory

---

## 3. Title options

Article:
1. My Code Reviewer Kept Suggesting Things We'd Already Said No To *(chosen)*
2. Store the Reaction, Not the Review: Giving a Code Reviewer Memory
3. A Code Reviewer That Remembers Why You Said No
4. Teaching an AI Reviewer Our Team's Rules, One Rejection at a Time
5. Why Our AI Reviewer Stopped Repeating Itself

Video:
1. I Gave My AI Code Reviewer a Memory
2. This Code Reviewer Remembers What Your Team Rejected
3. AI Code Review That Learns From Every Accept and Reject

---

## 4. Thumbnail prompt (Google Nano Banana, upload your photo)

"Create a YouTube thumbnail, 16:9, 1280x720. Use the uploaded photo of me on the right third, looking at the camera with a curious expression, cleanly cut out. Left side: dark code editor background with a glowing purple brain icon above a code review comment card. One card is crossed out in red with the label 'REJECTED', and a second card has a green check. Large bold white text on the left: 'IT REMEMBERS'. Smaller text below: 'AI code review with memory'. High contrast, clean, modern tech style, no other text."
