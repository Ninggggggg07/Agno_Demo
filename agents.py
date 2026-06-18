from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.duckduckgo import DuckDuckGoTools

from schemas import EngagementReport

# openai/gpt-oss-20b is the reliable choice on Groq for tool-calling (per Agno_note.md §8) —
# small Llama models are flaky on tool calls.
MODEL_ID = "openai/gpt-oss-20b"


def build_trend_researcher() -> Agent:
    return Agent(
        name="Trend Researcher",
        model=Groq(id=MODEL_ID),
        description="You are a curriculum trend researcher for a tech education company.",
        instructions=[
            "You will be given a course topic and its current outline.",
            "Search the web for what is currently trending or considered must-know in that topic area.",
            "Compare what you find against the given outline.",
            "List specific topics, tools, or practices that are missing or outdated in the outline.",
            "Keep it concise: a short bullet list is enough.",
        ],
        # backend="duckduckgo" (Agno's default) 404s against the installed ddgs version — "auto" works.
        tools=[DuckDuckGoTools(enable_news=False, backend="auto")],
        markdown=True,
    )


def build_engagement_reviewer() -> Agent:
    return Agent(
        name="Engagement Reviewer",
        model=Groq(id=MODEL_ID),
        description="You are an instructional designer who judges whether course content is boring or engaging.",
        instructions=[
            "You will be given a course outline/content.",
            "Score how engaging it is from 1 (boring) to 10 (highly engaging).",
            "List specific sections that feel dull, dense, or hard to follow.",
            "Give concrete suggestions to make it more engaging (examples, stories, interactivity, etc).",
        ],
        output_schema=EngagementReport,
    )
