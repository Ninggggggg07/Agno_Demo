import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agno.models.groq import Groq
from agno.run.base import RunStatus
from agno.skills import LocalSkills, Skills
from agno.team import Team
from agno.team.mode import TeamMode

from agents import MODEL_ID, build_engagement_reviewer, build_trend_researcher
from pdf_utils import extract_pdf_text


def build_course_director() -> Team:
    return Team(
        members=[build_trend_researcher(), build_engagement_reviewer()],
        model=Groq(id=MODEL_ID),
        name="Course Director",
        # broadcast = same brief to both reviewers at once; each applies their own
        # half of the rubric. Genuinely concurrent only via arun(stream=False) —
        # team.run() executes members sequentially under the hood.
        mode=TeamMode.broadcast,
        skills=Skills(loaders=[LocalSkills("skills/content-review-rubric")]),
        description="You are the director overseeing course quality at a tech education company.",
        instructions=[
            "You will receive a course name and its current outline/content.",
            "Use the content-review-rubric skill to brief your two reviewers, then delegate "
            "the same course name + outline to both of them so each applies their own half of the rubric "
            "(currency vs engagement).",
            "Once both reports come back, synthesize them into one Course Health verdict with three parts:",
            "1. Topics/practices to add or update for currency",
            "2. Sections to rewrite for engagement",
            "3. An overall recommendation: ship as-is / revise / overhaul",
            "Courses reviewed so far this session: {courses_reviewed}",
        ],
        session_state={"courses_reviewed": []},
        add_session_state_to_context=True,
        markdown=True,
    )


async def review_course(director: Team, course_name: str, course_content: str):
    message = f"Course: {course_name}\n\nCurrent outline/content:\n{course_content}"
    response = await director.arun(message, stream=False)
    if response.status == RunStatus.completed:
        director.session_state.setdefault("courses_reviewed", []).append(course_name)
    return response


async def main():
    director = build_course_director()

    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        course_name = Path(pdf_path).stem
        course_content = extract_pdf_text(pdf_path)
        result = await review_course(director, course_name, course_content)
        print(result.content)
        print("\n--- session_state ---")
        print(director.session_state)
        return

    result1 = await review_course(
        director,
        "Intro to Web Development",
        "HTML basics, CSS basics, jQuery for interactivity, deploying via FTP to a shared host.",
    )
    print(result1.content)
    print("\n--- session_state after course 1 ---")
    print(director.session_state)

    result2 = await review_course(
        director,
        "Data Structures 101",
        "Arrays and linked lists explained via 60-slide lecture, no coding exercises, final exam is the only assessment.",
    )
    print("\n\n" + "=" * 60)
    print(result2.content)
    print("\n--- session_state after course 2 ---")
    print(director.session_state)


if __name__ == "__main__":
    asyncio.run(main())
