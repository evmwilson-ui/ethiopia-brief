"""
Ethiopia Political Brief — Automated Newsletter Generator
Requires: pip install anthropic
"""

import anthropic
import json
import os
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─── CONFIG ───────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
RECIPIENTS = os.environ.get("RECIPIENTS", "").split(",")
MODEL = "claude-sonnet-4-6"
# ─────────────────────────────────────────────────────────────────────


def generate_newsletter():
    """Use Claude with web search to research and generate the newsletter."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    today = datetime.now().strftime("%B %d, %Y")
    cutoff = (datetime.now() - timedelta(hours=48)).strftime("%B %d, %Y")

    prompt = f"""You are a newsletter researcher and writer. Your task is to produce a
structured JSON object containing the most significant Ethiopian political stories
from the past 48 hours (since {cutoff}). Today is {today}.

RESEARCH INSTRUCTIONS:
- Search for recent Ethiopian politics news, elections, NEBE, press freedom,
  diplomacy, Ethiopia-Eritrea tensions, EPPJC, and political party developments.
- Run at least 4-5 separate searches to ensure comprehensive coverage.
- Focus on stories from the past 48 hours. Include older stories only if they are
  major ongoing developments with new updates in the window.
- For each story, you MUST include the actual source URL(s).

OUTPUT FORMAT — return ONLY valid JSON, no markdown, no backticks:
{{
  "date": "{today}",
  "stories": [
    {{
      "category": "Elections & Courts",
      "is_breaking": true,
      "headline": "Short, clear headline",
      "summary": "2-3 sentence summary of the story. Be factual and concise.",
      "sources": [
        {{"name": "Addis Standard", "url": "https://..."}},
        {{"name": "The Reporter", "url": "https://..."}}
      ]
    }}
  ]
}}

RULES:
- Include 4-8 stories, ordered by significance.
- Each summary must be 2-3 sentences, factual, no editorializing.
- Category labels should be short: "Elections & Courts", "Press Freedom",
  "Diplomacy", "Security", "Economy", "Political Parties", "Election Infrastructure", etc.
- Set is_breaking to true only for the top 1-2 most significant stories.
- Every story MUST have at least one source with a real URL from your search results.
- Return ONLY the JSON object. No preamble, no explanation, no markdown fences."""

    messages = [{"role": "user", "content": prompt}]
    all_text = ""
    max_rounds = 15

    for round_num in range(max_rounds):
        print(f"  API call {round_num + 1}...")

        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        assistant_content = response.content
        for block in assistant_content:
            if block.type == "text":
                all_text += block.text

        if response.stop_reason != "tool_use":
            print(f"  Done (stop_reason: {response.stop_reason})")
            break

        messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for block in assistant_content:
            if block.type == "tool_use":
                print(f"    Tool call: {block.name}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Search completed.",
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    json_text = all_text.strip()

    if not json_text:
        print("ERROR: No text returned from API. Response content types:")
        for block in response.content:
            print(f"  - {block.type}")
        raise RuntimeError("Claude did not return any text. Check your API key and model name.")

    json_text = re.sub(r"^```(?:json)?\s*", "", json_text)
    json_text = re.sub(r"\s*```$", "", json_text)

    match = re.search(r"\{.*\}", json_text, re.DOTALL)
    if match:
        json_text = match.group(0)

    return json.loads(json_text)


def build_html(data):
    """Convert the structured data into the newsletter HTML."""
    date = data["date"]
    stories = data["stories"]

    stories_html = ""
    for story in stories:
        source_links = " &middot; ".join(
            f'<a href="{s["url"]}">{s["name"]}</a>' for s in story["sources"]
        )
        label_class = "breaking" if story.get("is_breaking") else ""

        stories_html += f"""
  <div class="story">
    <div class="story-label {label_class}">{story["category"]}</div>
    <h2>{story["headline"]}</h2>
    <p>{story["summary"]}</p>
    <div class="source">{source_links}</div>
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ethiopia Political Brief &mdash; {date}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&family=Source+Sans+3:wght@400;500;600&display=swap');
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Source Sans 3', sans-serif;
      color: #1a1a1a;
      background: #f7f6f3;
      line-height: 1.6;
    }}
    .container {{
      max-width: 640px;
      margin: 0 auto;
      background: #ffffff;
    }}
    .header {{
      padding: 40px 32px 28px;
      border-bottom: 3px solid #1a1a1a;
    }}
    .header h1 {{
      font-family: 'Source Serif 4', serif;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      margin-bottom: 8px;
    }}
    .header .meta {{
      font-size: 13px;
      color: #666;
    }}
    .intro {{
      padding: 20px 32px;
      font-size: 13px;
      color: #888;
      border-bottom: 1px solid #e8e6e1;
      font-style: italic;
    }}
    .story {{
      padding: 24px 32px;
      border-bottom: 1px solid #e8e6e1;
    }}
    .story:last-of-type {{
      border-bottom: none;
    }}
    .story-label {{
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #999;
      margin-bottom: 6px;
    }}
    .story-label.breaking {{
      color: #c0392b;
    }}
    .story h2 {{
      font-family: 'Source Serif 4', serif;
      font-size: 17px;
      font-weight: 600;
      line-height: 1.4;
      margin-bottom: 10px;
    }}
    .story p {{
      font-size: 14.5px;
      color: #333;
      line-height: 1.65;
      margin-bottom: 8px;
    }}
    .story .source {{
      font-size: 12.5px;
      color: #888;
      margin-top: 4px;
    }}
    .story .source a {{
      color: #2a6496;
      text-decoration: none;
    }}
    .story .source a:hover {{
      text-decoration: underline;
    }}
    .footer {{
      padding: 24px 32px;
      border-top: 3px solid #1a1a1a;
      font-size: 12px;
      color: #999;
      text-align: center;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Ethiopia Political Brief</h1>
    <div class="meta">{date}</div>
  </div>
  <div class="intro">
    Significant political developments in Ethiopia over the past 48 hours. Sources are linked below each item.
  </div>
{stories_html}
  <div class="footer">
    Ethiopia Political Brief &middot; Prepared by KrF International Department<br>
    For questions or to unsubscribe, contact the editor.
  </div>
</div>
</body>
</html>"""

    return html


def send_email(html, date):
    """Send the newsletter via Gmail SMTP using app password."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Ethiopia Political Brief — {date}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENTS, msg.as_string())
        print(f"Email sent to {', '.join(RECIPIENTS)}")
    except Exception as e:
        print(f"Email delivery failed: {e}")


def save_html(html, date):
    """Save the newsletter as a local HTML file."""
    safe_date = date.replace(" ", "_").replace(",", "")
    filename = f"ethiopia_brief_{safe_date}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved: {filename}")
    return filename


# ─── MAIN ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Researching stories...")
    data = generate_newsletter()

    print(f"Found {len(data['stories'])} stories. Building HTML...")
    html = build_html(data)

    filename = save_html(html, data["date"])
    send_email(html, data["date"])

    print("Done.")
